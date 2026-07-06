/**
 * Análisis.com — Endpoint /api/ask (Cloudflare Worker)  ·  T15
 * ===========================================================
 * Responde cualquier pregunta elaborando la respuesta con información INTERNA
 * (search-index.json del sitio) + WEB (herramienta web_search de Claude), cita
 * las fuentes externas y lista los artículos de Análisis relacionados.
 *
 * Seguridad/costo: CORS restringido, rate limit por IP + caché (KV), tope diario
 * de gasto y (opcional) Cloudflare Turnstile. Degrada con gracia: ante límite,
 * error o falta de clave devuelve {degrade:true} y el front usa el modo interno.
 *
 * Requiere (wrangler.toml): binding KV `ASK_KV`; secret `ANTHROPIC_API_KEY`;
 * opcional `TURNSTILE_SECRET`. Vars opcionales: SITE, MODEL, RATE_PER_HOUR,
 * DAILY_CALL_CAP, ALLOWED_ORIGINS.
 */

const DEFAULTS = {
  SITE: "https://www.analisis.com",
  MODEL: "claude-sonnet-5",
  RATE_PER_HOUR: 20,     // consultas por IP por hora
  DAILY_CALL_CAP: 20,    // llamadas IA (no cacheadas) por día -> respeta el tope de gasto
  CACHE_TTL: 21600,      // 6 h de caché por pregunta normalizada
  MAX_Q: 500,            // largo máximo de la pregunta
};

const SYSTEM_PROMPT =
  "Eres el asistente de Análisis.com, portal de economía de América Latina. " +
  "Responde en español neutro SINTETIZANDO CON TUS PROPIAS PALABRAS (nunca pegues frases " +
  "de los resultados de búsqueda). Formato: 1 o 2 frases de contexto y, si aporta, 2 o 3 " +
  "viñetas MUY cortas, cada una en UNA sola línea que empieza con '- ' seguida del texto. " +
  "Directo al grano: sin preámbulos, saludos, relleno, URLs, enlaces ni sección de fuentes, " +
  "y sin markdown de negrita (**). Máximo 80 palabras en total.";

export default {
  async fetch(request, env, ctx) {
    const cfg = { ...DEFAULTS, ...numify(env) };
    const origin = request.headers.get("Origin") || "";
    const cors = corsHeaders(origin, env);

    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    const url = new URL(request.url);
    if (request.method !== "POST") return json({ error: "method" }, 405, cors);
    if (url.pathname === "/api/translate")
      return handleTranslate(request, env, ctx, cors);
    if (url.pathname !== "/api/ask") return json({ error: "not found" }, 404, cors);

    // --- entrada ---
    let body;
    try { body = await request.json(); } catch { return json({ error: "bad json" }, 400, cors); }
    const q = String(body.q || "").trim().slice(0, cfg.MAX_Q);
    if (q.length < 3) return json({ error: "Escribe una pregunta un poco más larga." }, 400, cors);

    // --- rate limit por IP ---
    const ip = request.headers.get("CF-Connecting-IP") || "anon";
    const rlKey = `rl:${ip}:${Math.floor(Date.now() / 3600000)}`;
    const rl = parseInt((await env.ASK_KV.get(rlKey)) || "0", 10);
    if (rl >= cfg.RATE_PER_HOUR)
      return json({ error: "Has alcanzado el límite por hora. Intenta más tarde." }, 429, cors);

    // --- Turnstile (opcional) ---
    if (env.TURNSTILE_SECRET) {
      const ok = await verifyTurnstile(body.token, ip, env.TURNSTILE_SECRET);
      if (!ok) return json({ error: "Verificación anti-bot fallida." }, 403, cors);
    }

    // --- caché por pregunta normalizada ---
    const cacheKey = `ans:${await sha256(q.toLowerCase())}`;
    const cached = await env.ASK_KV.get(cacheKey);
    if (cached) return json(JSON.parse(cached), 200, cors);

    // --- tope diario de gasto -> degradar ---
    const dayKey = `spend:${new Date().toISOString().slice(0, 10)}`;
    const spend = parseInt((await env.ASK_KV.get(dayKey)) || "0", 10);
    if (spend >= cfg.DAILY_CALL_CAP)
      return json({ degrade: true, error: "El asistente está muy solicitado hoy." }, 200, cors);

    // sin clave -> el front usa el modo interno
    if (!env.ANTHROPIC_API_KEY) return json({ degrade: true }, 200, cors);

    // --- recuperación interna (artículos relacionados) ---
    const related = await retrieveInternal(q, cfg.SITE, ctx);

    // --- Claude con web_search ---
    let result;
    try {
      result = await askClaude(q, related, cfg, env.ANTHROPIC_API_KEY);
    } catch (e) {
      return json({ degrade: true, error: "No pude consultar ahora." }, 200, cors);
    }
    result.related = related;

    ctx.waitUntil(env.ASK_KV.put(rlKey, String(rl + 1), { expirationTtl: 3700 }));
    ctx.waitUntil(env.ASK_KV.put(dayKey, String(spend + 1), { expirationTtl: 90000 }));
    ctx.waitUntil(env.ASK_KV.put(cacheKey, JSON.stringify(result), { expirationTtl: cfg.CACHE_TTL }));

    return json(result, 200, cors);
  },
};

// ------------------------------------------------------------ traducción (T-idiomas)
const LANG_NAME = { en: "English", pt: "Brazilian Portuguese", de: "German" };

async function handleTranslate(request, env, ctx, cors) {
  let body;
  try { body = await request.json(); } catch { return json({ error: "bad json" }, 400, cors); }
  const lang = String(body.lang || "").slice(0, 2);
  const texts = Array.isArray(body.texts)
    ? body.texts.slice(0, 80).map((t) => String(t || "").slice(0, 4000)) : null;
  if (!texts || !texts.length || !LANG_NAME[lang])
    return json({ error: "bad params" }, 400, cors);
  if (!env.ANTHROPIC_API_KEY) return json({ degrade: true }, 200, cors);

  // caché permanente por (idioma + contenido): las notas no cambian.
  const key = `tr:${lang}:${await sha256(texts.join(""))}`;
  const cached = await env.ASK_KV.get(key);
  if (cached) return json({ t: JSON.parse(cached) }, 200, cors);

  // tope diario de traducciones (barato; separado del asistente)
  const dayKey = `trspend:${new Date().toISOString().slice(0, 10)}`;
  const cap = parseInt(env.TRANSLATE_CAP || "500", 10);
  const spend = parseInt((await env.ASK_KV.get(dayKey)) || "0", 10);
  if (spend >= cap) return json({ degrade: true }, 200, cors);

  try {
    const out = await translateTexts(texts, lang, env.ANTHROPIC_API_KEY);
    ctx.waitUntil(env.ASK_KV.put(key, JSON.stringify(out)));            // sin TTL: permanente
    ctx.waitUntil(env.ASK_KV.put(dayKey, String(spend + 1), { expirationTtl: 90000 }));
    return json({ t: out }, 200, cors);
  } catch (e) {
    return json({ degrade: true }, 200, cors);
  }
}

async function translateTexts(texts, lang, apiKey) {
  const payload = {
    model: "claude-haiku-4-5",
    max_tokens: 3000,
    system: "Eres un traductor profesional de noticias. Traduce cada elemento del "
      + "array JSON de entrada al idioma indicado, conservando el significado, el tono "
      + "y todas las cifras, nombres y fechas. Devuelve el objeto {\"t\": [...]} con las "
      + "traducciones en el MISMO orden y misma longitud. No añadas nada más. Idioma destino: "
      + LANG_NAME[lang] + ".",
    messages: [{ role: "user", content: JSON.stringify(texts) }],
    output_config: {
      format: {
        type: "json_schema",
        schema: {
          type: "object",
          properties: { t: { type: "array", items: { type: "string" } } },
          required: ["t"], additionalProperties: false,
        },
      },
    },
  };
  const data = await callAnthropic(payload, apiKey);
  const arr = (JSON.parse(extractText(data)) || {}).t;
  if (!Array.isArray(arr) || arr.length !== texts.length) throw new Error("bad translation");
  return arr;
}

// ------------------------------------------------------------ recuperación interna
async function retrieveInternal(q, site, ctx) {
  try {
    const r = await fetch(`${site}/search-index.json`, { cf: { cacheTtl: 900 } });
    const idx = await r.json();
    const terms = norm(q).split(/\s+/).filter((t) => t.length >= 3);
    const scored = idx.map((a) => {
      const hay = norm(`${a.title} ${a.subtitle} ${a.text} ${(a.tags || []).join(" ")}`);
      let sc = 0;
      for (const t of terms) {
        sc += hay.split(t).length - 1;
        if (norm(a.title).includes(t)) sc += 3;
      }
      return { a, sc };
    }).filter((x) => x.sc > 0).sort((x, y) => y.sc - x.sc).slice(0, 5);
    return scored.map((x) => ({
      title: x.a.title, url: `${site}/${x.a.url}`,
      section: x.a.sectionName || x.a.section, date: x.a.dateLong || x.a.date,
    }));
  } catch { return []; }
}

// ------------------------------------------------------------ Claude + web_search
async function askClaude(q, related, cfg, apiKey) {
  const contexto = related.length
    ? "\n\nARTÍCULOS DE ANÁLISIS.COM POSIBLEMENTE RELACIONADOS (tenlos en cuenta):\n" +
      related.map((a) => `- ${a.title} (${a.section}, ${a.date})`).join("\n")
    : "";
  const payload = {
    model: cfg.MODEL,
    max_tokens: 500,
    system: SYSTEM_PROMPT,
    // thinking desactivado + pocas búsquedas -> respuesta en segundos (dentro del
    // presupuesto del Worker). Sonnet 5 acepta {type:"disabled"}.
    thinking: { type: "disabled" },
    tools: [{ type: "web_search_20250305", name: "web_search", max_uses: 2 }],
    messages: [{ role: "user", content: `Pregunta: ${q}${contexto}` }],
  };
  const t0 = Date.now();
  let data = await callAnthropic(payload, apiKey);
  // el bucle server-side puede pausar; se reanuda re-enviando (una vez)
  if (data.stop_reason === "pause_turn") {
    payload.messages.push({ role: "assistant", content: data.content });
    data = await callAnthropic(payload, apiKey);
  }
  console.log(`ask ok ${Date.now() - t0}ms stop=${data.stop_reason}`);
  return { answer: extractText(data), sources: extractSources(data) };
}

async function callAnthropic(payload, apiKey) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 30000); // corta si tarda demasiado
  try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      signal: ctrl.signal,
      headers: {
        "content-type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(`anthropic ${r.status}`);
    return r.json();
  } finally {
    clearTimeout(t);
  }
}

function extractText(data) {
  // Con web_search el texto llega en muchos bloques (uno por cita); se unen SIN
  // separador para no partir frases. Los saltos de línea reales (viñetas) van
  // dentro del texto de cada bloque y se conservan.
  return (data.content || [])
    .filter((b) => b.type === "text").map((b) => b.text).join("").trim();
}

function extractSources(data) {
  const out = [], seen = new Set();
  for (const b of data.content || []) {
    if (b.type !== "web_search_tool_result" || !Array.isArray(b.content)) continue;
    for (const it of b.content) {
      if (it.type === "web_search_result" && it.url && !seen.has(it.url)) {
        seen.add(it.url);
        out.push({ title: it.title || it.url, url: it.url });
      }
    }
  }
  return out.slice(0, 6);
}

// ------------------------------------------------------------ utilidades
function corsHeaders(origin, env) {
  const allowed = (env.ALLOWED_ORIGINS ||
    "https://www.analisis.com,https://analisis.com").split(",").map((s) => s.trim());
  const ok = allowed.includes(origin);
  return {
    "Access-Control-Allow-Origin": ok ? origin : allowed[0],
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Max-Age": "86400",
  };
}

async function verifyTurnstile(token, ip, secret) {
  if (!token) return false;
  try {
    const form = new FormData();
    form.append("secret", secret);
    form.append("response", token);
    form.append("remoteip", ip);
    const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify",
      { method: "POST", body: form });
    return (await r.json()).success === true;
  } catch { return false; }
}

const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
function json(obj, status, cors) {
  return new Response(JSON.stringify(obj),
    { status, headers: { "content-type": "application/json", ...cors } });
}
function numify(env) {
  const out = {};
  for (const k of ["RATE_PER_HOUR", "DAILY_CALL_CAP", "CACHE_TTL", "MAX_Q"])
    if (env[k] != null && env[k] !== "") out[k] = parseInt(env[k], 10);
  for (const k of ["SITE", "MODEL"]) if (env[k]) out[k] = env[k];
  return out;
}
async function sha256(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
