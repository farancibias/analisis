# Endpoint `/api/ask` — asistente IA de Análisis.com (T15)

Backend serverless (Cloudflare Worker) que responde cualquier pregunta combinando
**información interna** (`search-index.json` del sitio) con **búsqueda web** (la
herramienta `web_search` de Claude), citando fuentes externas y listando los
artículos de Análisis relacionados.

- **Modelo:** `claude-sonnet-5` (configurable con la var `MODEL`).
- **Búsqueda web:** integrada en Claude (`web_search`) — no requiere otro proveedor.
- **Seguridad/costo:** CORS restringido a analisis.com, rate limit por IP + caché
  (KV), tope diario de gasto (`DAILY_CALL_CAP`) y Turnstile opcional.
- **Degrada con gracia:** ante límite, error o falta de clave devuelve
  `{degrade:true}` y el front (`ASK_JS`) usa el modo interno (extractivo sobre
  `search-index.json`), sin romperse.

## Contrato

`POST /api/ask`  ·  body `{ "q": "<pregunta>", "token": "<turnstile opcional>" }`

```json
{
  "answer": "texto elaborado en español...",
  "sources": [ { "title": "...", "url": "https://..." } ],
  "related": [ { "title": "...", "url": "https://www.analisis.com/articulo/....html", "section": "...", "date": "..." } ]
}
```
(o `{ "degrade": true }` para que el front caiga al modo interno.)

## Despliegue (una vez)

Requiere que `analisis.com` esté en Cloudflare (ya lo está) y Node + `wrangler`.

```bash
cd worker
npm i -g wrangler          # si no lo tienes
wrangler login             # abre el navegador; autoriza tu cuenta

# 1) Crear el namespace KV y pegar el id en wrangler.toml (kv_namespaces.id)
wrangler kv namespace create ASK_KV

# 2) Cargar la clave de Anthropic (la misma que ya rotaste)
wrangler secret put ANTHROPIC_API_KEY
#   (opcional anti-bots) wrangler secret put TURNSTILE_SECRET

# 3) Publicar
wrangler deploy
```

Prueba:
```bash
curl -s https://www.analisis.com/api/ask -H 'content-type: application/json' \
  -d '{"q":"¿Cómo va el precio del cobre?"}' | jq
```

## Conectar el front

El sitio ya trae el hook. Publica el sitio con la variable de build **`ASK_URL`**
apuntando al endpoint para activar el modo IA en la portada y en `/asistente.html`:

```
ASK_URL=https://www.analisis.com/api/ask
```

(en el workflow de GitHub Actions, como variable del repo). Sin `ASK_URL`, el
asistente funciona en modo interno.

## Costo y límites

- Tope duro diario: `DAILY_CALL_CAP` llamadas IA no cacheadas/día (por defecto 20,
  calibrado a ~US$20/mes). Al superarlo, el endpoint degrada al modo interno.
- `RATE_PER_HOUR` consultas por IP/hora (por defecto 20).
- Caché de 6 h por pregunta normalizada: las repetidas no re-pagan.
- Turnstile (opcional): si defines `TURNSTILE_SECRET`, el front debe enviar `token`.
