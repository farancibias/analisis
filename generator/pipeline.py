#!/usr/bin/env python3
"""
Pipeline editorial automatizado de Análisis.com  (ESQUELETO FUNCIONAL)
=====================================================================
Este script define el flujo que corre cada 24 h para poblar el portal.
Está estructurado en 5 etapas. Las etapas 1 y 2 (recolección y
agrupación) están implementadas de forma funcional con feeds RSS
públicos. La etapa 3 (redacción original con IA) está marcada con el
punto exacto donde se conecta un modelo de lenguaje mediante API.

Flujo:
  1. RECOLECTAR  -> descargar titulares/resúmenes de fuentes fiables (RSS)
  2. AGRUPAR     -> detectar la MISMA noticia cubierta por >=2 fuentes
  3. REDACTAR    -> con el contexto de todas las fuentes, escribir un
                    artículo NUEVO y original (no copia, no cita textual)
  4. GUARDAR     -> añadir el artículo a content/articles.json (archivo)
  5. PUBLICAR    -> build.py regenera el sitio estático

Requisitos:  pip install feedparser
             (para la etapa 3, el SDK del proveedor de IA que uses)
"""

import json
import os
import re
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content", "articles.json")
SOURCES = os.path.join(ROOT, "generator", "sources.json")

# umbral de similitud de titulares para considerar que dos notas hablan de lo mismo
SIMILARITY = 0.42
# nº mínimo de fuentes distintas para considerar un tema "contrastado" (se prioriza)
MIN_SOURCES = 2
# nº de notas a generar por CADA sección en cada tanda
PER_SECTION = int(os.environ.get("PIPELINE_PER_SECTION") or "2")

# Modelo de redacción (configurable). Por defecto Claude Opus 4.8.
# Nota: se usa `or` (no el default de get) porque el workflow puede pasar la
# variable como cadena VACÍA cuando no está definida en el repo.
MODEL = os.environ.get("PIPELINE_MODEL") or "claude-opus-4-8"
MAX_TOKENS = int(os.environ.get("PIPELINE_MAX_TOKENS") or "8000")

# --- Modo prueba controlada ---
# PIPELINE_LIMIT: nº máximo de notas a redactar por corrida (0 = sin límite).
# PIPELINE_DRY_RUN=1: genera y MUESTRA las notas en el log, sin guardarlas ni publicar.
PIPELINE_LIMIT = int(os.environ.get("PIPELINE_LIMIT") or "0")
PIPELINE_DRY_RUN = os.environ.get("PIPELINE_DRY_RUN", "") == "1"


# ------------------------------------------------------------- 1. RECOLECTAR
def recolectar(sources):
    """Descarga entradas recientes de cada feed RSS. Devuelve lista de dicts."""
    import feedparser  # import diferido para que el esqueleto cargue sin la dep
    items = []
    for src in sources:
        feed = feedparser.parse(src["url"])
        for e in feed.entries[: src.get("max", 15)]:
            items.append({
                "source": src["name"],
                "region": src["region"],
                "section_hint": src.get("section"),
                "title": e.get("title", "").strip(),
                "summary": re.sub("<[^>]+>", "", e.get("summary", "")).strip(),
                "link": e.get("link", ""),
                "published": e.get("published", ""),
            })
    return items


# --------------------------------------------------------------- 2. AGRUPAR
def _norm(t):
    return re.sub(r"[^a-záéíóúñ0-9 ]", "", t.lower())


def _tokens(t):
    """Palabras 'significativas' del título (entidades/temas): >= 5 letras."""
    return {w for w in _norm(t).split() if len(w) >= 5}


def _similar(a, b):
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _misma_noticia(a, b):
    """Dos notas hablan de lo mismo si comparten al menos una palabra
    significativa (entidad/tema) Y sus titulares se parecen. La condición del
    token compartido evita agrupar historias distintas de estructura parecida."""
    if not (_tokens(a["title"]) & _tokens(b["title"])):
        return False
    return _similar(a["title"], b["title"]) >= SIMILARITY


def _seccion(cluster):
    """Sección del grupo por mayoría de las fuentes (no la del primer feed)."""
    cnt = Counter(i.get("section_hint") for i in cluster if i.get("section_hint"))
    return cnt.most_common(1)[0][0] if cnt else "internacional"


def _clusterizar(items):
    """Agrupa por misma noticia; devuelve TODOS los grupos (incl. de una fuente)."""
    clusters = []
    for it in items:
        for c in clusters:
            if _misma_noticia(it, c[0]):
                c.append(it)
                break
        else:
            clusters.append([it])
    return clusters


# ---- Relevancia regional (LatAm) y filtro de no-noticias (T2) ----
# Señales de que una nota importa a América Latina. Se eligen términos
# DISTINTIVOS (países, región y empresas emblemáticas) evitando palabras
# genéricas ("real", "sol", "peso", "vale") que darían falsos positivos.
REGION_TERMS = {
    "chile", "chileno", "chilena", "argentina", "argentino", "brasil",
    "brasileño", "brasileno", "brasilena", "méxico", "mexico", "mexicano",
    "perú", "peru", "peruano", "colombia", "colombiano", "uruguay", "uruguayo",
    "paraguay", "bolivia", "boliviano", "ecuador", "ecuatoriano", "venezuela",
    "venezolano", "panamá", "panama", "guatemala", "honduras", "nicaragua",
    "república dominicana", "dominicana", "latinoamérica", "latinoamerica",
    "latam", "américa latina", "america latina", "sudamérica", "sudamerica",
    "mercosur", "alianza del pacífico", "codelco", "petrobras", "pemex",
    "ecopetrol", "falabella", "cencosud", "mercadolibre", "mercado libre",
    "nubank", "itaú", "itau", "bradesco", "bancolombia", "cmpc", "arauco",
    "antofagasta", "escondida", "copec", "enap", "américa móvil",
    "america movil", "cemex", "femsa", "bimbo", "ypf",
}

# Patrones de "no-noticia". Se separan en dos: frases inequívocas (se buscan en
# cualquier parte) y ETIQUETAS de sección ambiguas (opinión/editorial/columna...)
# que solo cuentan si aparecen como rótulo (inicio del título o tras | - : ),
# para no descartar notas legítimas con "la opinión pública", etc.
NONEWS_RE = re.compile(
    r"(cartas? al director|cartas? del lector|letters to the editor|en vivo|"
    r"minuto a minuto|as[íi] lo vivimos|live ?blog|obituari|necrol[óo]gic|"
    r"\bobituary\b|horóscopo|horoscopo|crucigrama|pasatiempo)", re.I)
NONEWS_LABEL_RE = re.compile(
    r"(^|[|\-–—:])\s*(opini[óo]n|opinion|editorial|columna|tribuna|comment)\b", re.I)


def _norm_txt(t):
    return re.sub(r"[^a-záéíóúñü0-9 ]", " ", (t or "").lower())


def puntaje_regional(texto):
    """Nº de señales regionales DISTINTAS en el texto (0 = sin foco LatAm)."""
    n = _norm_txt(texto)
    return sum(1 for term in REGION_TERMS if term in n)


# Países LatAm por código ISO -> términos DISTINTIVOS (país, gentilicio, capital,
# empresas/figuras emblemáticas). Se usan para priorizar la portada según el país
# del lector (T5). Se evitan términos ambiguos ("real", "vale", "petro", "peso").
COUNTRIES = {
    "cl": ["chile", "chileno", "chilena", "santiago", "codelco", "sqm",
           "cencosud", "falabella", "copec", "enap", "cmpc", "arauco",
           "antofagasta", "escondida", "banco de chile"],
    "ar": ["argentina", "argentino", "argentina", "buenos aires", "ypf",
           "milei", "merval", "banco nación"],
    "br": ["brasil", "brasileño", "brasileña", "brasilena", "sao paulo",
           "são paulo", "petrobras", "bradesco", "itaú", "itau", "nubank",
           "bovespa", "lula", "río de janeiro"],
    "mx": ["méxico", "mexico", "mexicano", "mexicana", "pemex", "cemex",
           "femsa", "bimbo", "banxico", "ciudad de méxico"],
    "pe": ["perú", "peru", "peruano", "peruana", "lima"],
    "co": ["colombia", "colombiano", "colombiana", "bogotá", "bogota",
           "ecopetrol", "bancolombia"],
    "uy": ["uruguay", "uruguayo", "montevideo"],
    "py": ["paraguay", "paraguayo", "asunción", "asuncion"],
    "bo": ["bolivia", "boliviano", "la paz"],
    "ec": ["ecuador", "ecuatoriano", "quito", "guayaquil"],
    "ve": ["venezuela", "venezolano", "caracas", "pdvsa"],
}


PAIS_NOMBRE = {
    "cl": "Chile", "ar": "Argentina", "br": "Brasil", "mx": "México",
    "pe": "Perú", "co": "Colombia", "uy": "Uruguay", "py": "Paraguay",
    "bo": "Bolivia", "ec": "Ecuador", "ve": "Venezuela",
}

# Empresas/entidades emblemáticas de LatAm para los hubs (T9). Solo nombres
# DISTINTIVOS (se evitan términos ambiguos como "vale" o "santander").
EMPRESAS = {
    "codelco": {"name": "Codelco", "terms": ["codelco"]},
    "petrobras": {"name": "Petrobras", "terms": ["petrobras"]},
    "ypf": {"name": "YPF", "terms": ["ypf"]},
    "pemex": {"name": "Pemex", "terms": ["pemex"]},
    "ecopetrol": {"name": "Ecopetrol", "terms": ["ecopetrol"]},
    "falabella": {"name": "Falabella", "terms": ["falabella"]},
    "cencosud": {"name": "Cencosud", "terms": ["cencosud"]},
    "mercadolibre": {"name": "MercadoLibre", "terms": ["mercadolibre", "mercado libre"]},
    "nubank": {"name": "Nubank", "terms": ["nubank"]},
    "bradesco": {"name": "Bradesco", "terms": ["bradesco"]},
    "itau": {"name": "Itaú", "terms": ["itaú", "itau"]},
    "bancolombia": {"name": "Bancolombia", "terms": ["bancolombia"]},
    "cmpc": {"name": "CMPC", "terms": ["cmpc"]},
    "arauco": {"name": "Arauco", "terms": ["arauco"]},
    "sqm": {"name": "SQM", "terms": ["sqm"]},
    "cemex": {"name": "Cemex", "terms": ["cemex"]},
    "femsa": {"name": "Femsa", "terms": ["femsa"]},
    "bimbo": {"name": "Bimbo", "terms": ["bimbo"]},
    "copec": {"name": "Copec", "terms": ["copec"]},
}


def paises_de(texto):
    """Códigos ISO de país mencionados en el texto (para personalizar portada)."""
    n = _norm_txt(texto)
    return sorted(code for code, terms in COUNTRIES.items()
                  if any(t in n for t in terms))


def empresas_de(texto):
    """Slugs de empresas/entidades emblemáticas mencionadas (para los hubs T9)."""
    n = _norm_txt(texto)
    return sorted(slug for slug, info in EMPRESAS.items()
                  if any(t in n for t in info["terms"]))


def es_no_noticia(item):
    """True si el título parece opinión, carta, live-blog, obituario o pasatiempo."""
    t = item.get("title", "")
    return bool(NONEWS_RE.search(t) or NONEWS_LABEL_RE.search(t))


def _region_cluster(cluster):
    txt = " ".join(i.get("title", "") + " " + i.get("summary", "") for i in cluster)
    return puntaje_regional(txt)


def seleccionar_por_seccion(items, por_seccion):
    """Elige hasta `por_seccion` temas por CADA sección. Descarta no-noticias
    (opinión, cartas, live-blogs...) y prioriza los temas con mayor RELEVANCIA
    REGIONAL y más fuentes distintas; completa con lo más contrastado."""
    por_sec = defaultdict(list)
    for it in items:
        if es_no_noticia(it):
            continue  # fuera opinión, cartas al director, live-blogs, obituarios
        por_sec[it.get("section_hint") or "internacional"].append(it)
    elegidos = []
    for sec in sorted(por_sec):
        grupos = _clusterizar(por_sec[sec])
        # regional primero; a igualdad, el tema con más fuentes contrastadas.
        grupos.sort(key=lambda c: (_region_cluster(c),
                                   len({i["source"] for i in c})), reverse=True)
        elegidos.extend(grupos[:por_seccion])
    return elegidos


# -------------------------------------------------------------- 3. REDACTAR
SYSTEM_PROMPT = (
    "Eres redactor de Análisis.com, un portal de noticias serio en español "
    "(estilo editorial El País / WSJ). Redactas notas ORIGINALES, informativas "
    "y CONCRETAS en español neutro. Nunca copias ni parafraseas frases de las "
    "fuentes: sintetizas los hechos con tus propias palabras y aportas contexto."
)

REDACCION_PROMPT = """Tienes uno o varios resúmenes de UNA MISMA noticia (si hay más de una fuente, procede de distintos medios internacionales).

Redacta un artículo COMPLETAMENTE ORIGINAL en español que sintetice los hechos y aporte contexto.

Reglas:
- Usa SOLO hechos presentes en los resúmenes; NO inventes datos.
- Sé CONCRETO: incluye los NOMBRES PROPIOS, LUGARES, EMPRESAS, INSTITUCIONES, CIFRAS, PORCENTAJES y FECHAS que aparezcan en las fuentes (personas, países, ciudades, compañías, montos). Cuanto más específico, mejor; evita frases genéricas.
- Atribuye lo que provenga de una sola fuente ("según X").
- NO copies ni parafrasees frases: redacta desde cero.
- Tono informativo y contextualizado, sin opinión ni relleno.
- EXTENSIÓN: el cuerpo (body) debe tener entre 6 y 8 párrafos y en total unas 250-350 palabras (una nota desarrollada, no un resumen breve).

Entrega estos campos:
- title: titular claro y específico.
- subtitle: bajada de una frase.
- tags: 3 o 4 etiquetas (entidades o temas concretos, útiles para buscar una foto).
- key_points: 3 o 4 viñetas de "claves en 30 segundos".
- lead: 1 o 2 frases de entrada.
- body: lista de párrafos (6 a 8).
- image_prompt: descripción visual para una foto editorial, sin texto ni logos.
- image_alt: texto alternativo accesible de la imagen.
- image_query: 2 a 4 palabras clave EN INGLÉS para buscar una foto de archivo GENÉRICA y relacionada (objetos, lugares, industria, materiales, paisajes). PROHIBIDO incluir: nombres de personas o políticos, partidos, protestas, manifestaciones, banderas, elecciones, armas, policía o violencia. Ejemplos: "copper mine machinery", "shipping port containers", "office buildings finance".

RESÚMENES DE LAS FUENTES:
{fuentes}
"""

# Esquema para forzar una salida JSON válida (structured outputs).
_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "subtitle": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "lead": {"type": "string"},
        "body": {"type": "array", "items": {"type": "string"}},
        "image_prompt": {"type": "string"},
        "image_alt": {"type": "string"},
        "image_query": {"type": "string"},
    },
    "required": ["title", "subtitle", "tags", "key_points", "lead", "body",
                 "image_prompt", "image_alt", "image_query"],
    "additionalProperties": False,
}


def redactar(cluster):
    """Escribe un artículo original con Claude a partir del cluster de fuentes.

    Devuelve un dict con las claves del esquema, o None si la API falla (para
    que el pipeline continúe con los demás temas sin romperse).
    """
    import anthropic  # import diferido: sólo si se usa
    fuentes = "\n\n".join(
        f"[{i['source']}] {i['title']}\n{i['summary']}" for i in cluster)
    try:
        client = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user",
                       "content": REDACCION_PROMPT.format(fuentes=fuentes)}],
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        )
        texto = next((b.text for b in resp.content if b.type == "text"), "")
        return json.loads(texto)
    except Exception as e:  # noqa: BLE001
        print(f"  aviso: falló la redacción con IA ({e}); se omite este tema.")
        return None


# ---------------------------------------------------------------- 4. GUARDAR
def previsualizar(articulo_ia, section, cluster):
    """Imprime la nota generada (modo dry-run) para revisar calidad sin publicar."""
    palabras = sum(len(p.split()) for p in articulo_ia.get("body", []))
    print("\n" + "=" * 72)
    print(f"[PRUEBA · {section}]  {articulo_ia.get('title', '')}")
    print(f"  bajada: {articulo_ia.get('subtitle', '')}")
    print(f"  tags: {articulo_ia.get('tags', [])}")
    print(f"  fuentes: {sorted({i['source'] for i in cluster})}")
    print(f"  extensión: {len(articulo_ia.get('body', []))} párrafos · {palabras} palabras")
    print("  claves en 30s:")
    for k in articulo_ia.get("key_points", []):
        print(f"    - {k}")
    print("  cuerpo:")
    for p in articulo_ia.get("body", []):
        print(f"    {p}\n")
    print("=" * 72)


def guardar(articulo_ia, section, cluster):
    with open(CONTENT, encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-",
                  articulo_ia["title"].lower())[:60].strip("-")
    aid = f"{today}-{slug}-{hashlib.md5(articulo_ia['title'].encode()).hexdigest()[:6]}"
    if any(a["id"] == aid for a in data["articles"]):
        return None  # ya existe: evita duplicados
    body = articulo_ia.get("body") or []
    data["articles"].append({
        "id": aid,
        "section": section,
        "title": articulo_ia["title"],
        "subtitle": articulo_ia["subtitle"],
        "date": today,
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "author": "Redacción Análisis.com",
        "tags": articulo_ia.get("tags", []),
        "image_prompt": articulo_ia.get("image_prompt", ""),
        "image_alt": articulo_ia.get("image_alt") or articulo_ia["title"],
        "image_query": articulo_ia.get("image_query", ""),
        "key_points": articulo_ia.get("key_points", []),
        "lead": articulo_ia.get("lead") or (body[0] if body else ""),
        "body": body,
        "sources_consulted": sorted({i["source"] for i in cluster}),
        "region_score": puntaje_regional(
            articulo_ia["title"] + " " + (articulo_ia.get("subtitle") or "")
            + " " + " ".join(body) + " " + " ".join(articulo_ia.get("tags", []))),
        "countries": paises_de(
            articulo_ia["title"] + " " + (articulo_ia.get("subtitle") or "")
            + " " + " ".join(body) + " " + " ".join(articulo_ia.get("tags", []))),
        "companies": empresas_de(
            articulo_ia["title"] + " " + (articulo_ia.get("subtitle") or "")
            + " " + " ".join(body) + " " + " ".join(articulo_ia.get("tags", []))),
    })
    with open(CONTENT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return aid


# ---------------------------------------------------- 4b. RESUMEN DEL DÍA (T7)
DIGEST = os.path.join(ROOT, "content", "digest.json")

RESUMEN_PROMPT = """Eres el editor de Análisis.com. A partir de estos titulares y bajadas de la jornada, escribe una SÍNTESIS de 1 o 2 frases (máximo 45 palabras) que capte lo esencial del día para un lector de negocios en América Latina.

Reglas: español neutro, informativa, sin opinión, sin enumerar ni usar viñetas; una mirada de conjunto que conecte los temas principales. Devuelve SOLO el texto de la síntesis, sin encabezados.

TITULARES DE HOY:
{titulares}
"""


def generar_resumen_dia():
    """Escribe content/digest.json con una síntesis del día redactada por IA.
    Degrada a nada (no escribe) si falta la clave o la API falla: en ese caso el
    build muestra solo las 5 claves con enlaces, sin la frase de síntesis."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return
    try:
        with open(CONTENT, encoding="utf-8") as f:
            data = json.load(f)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        hoy = [a for a in data.get("articles", []) if a.get("date") == today]
        if not hoy:
            return
        hoy.sort(key=lambda a: (a.get("region_score", 0),
                                len(a.get("sources_consulted") or [])), reverse=True)
        titulares = "\n".join(
            f"- {a['title']}: {a.get('subtitle', '')}" for a in hoy[:8])
        import anthropic  # import diferido
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=MODEL, max_tokens=300,
            messages=[{"role": "user",
                       "content": RESUMEN_PROMPT.format(titulares=titulares)}])
        intro = next((b.text for b in resp.content if b.type == "text"), "").strip()
        if intro:
            with open(DIGEST, "w", encoding="utf-8") as f:
                json.dump({"date": today, "intro": intro}, f,
                          ensure_ascii=False, indent=2)
            print("      resumen del día escrito (content/digest.json).")
    except Exception as e:  # noqa: BLE001
        print(f"      aviso: no se generó el resumen del día ({e}).")


# -------------------------------------------------------------------- MAIN
def main():
    # La redacción con IA requiere la clave. Sin ANTHROPIC_API_KEY el pipeline
    # no toca articles.json (el sitio se publica con el contenido existente).
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("PIPELINE_LLM")):
        print("pipeline: sin ANTHROPIC_API_KEY -> no se generan artículos "
              "automáticos (se conserva el contenido actual). Añade el secret "
              "ANTHROPIC_API_KEY para activar la redacción con Claude.")
        return
    with open(SOURCES, encoding="utf-8") as f:
        sources = json.load(f)["feeds"]
    print(f"[1/5] Recolectando de {len(sources)} fuentes...")
    items = recolectar(sources)
    print(f"      {len(items)} entradas descargadas.")
    print(f"[2/5] Eligiendo hasta {PER_SECTION} temas por sección...")
    seleccion = seleccionar_por_seccion(items, PER_SECTION)
    reparto = Counter(_seccion(c) for c in seleccion)
    print(f"      {len(seleccion)} temas. Reparto por sección: {dict(sorted(reparto.items()))}")
    # Modo prueba: tope global de notas (además de la cuota por sección).
    if PIPELINE_LIMIT > 0:
        seleccion = seleccion[:PIPELINE_LIMIT]
        print(f"      modo prueba: se procesan {len(seleccion)} temas "
              f"(PIPELINE_LIMIT={PIPELINE_LIMIT}).")
    if PIPELINE_DRY_RUN:
        print("      DRY-RUN activo: se mostrarán las notas SIN guardarlas ni publicar.")
    print("[3/5] Redactando artículos originales...")
    nuevos = 0
    for c in seleccion:
        art = redactar(c)
        if not art:
            continue  # la IA falló para este tema: se omite, no se rompe el build
        section = _seccion(c)
        if PIPELINE_DRY_RUN:
            previsualizar(art, section, c)
            nuevos += 1
            continue
        if guardar(art, section, c):
            nuevos += 1
    if PIPELINE_DRY_RUN:
        print(f"      MODO PRUEBA: {nuevos} nota(s) generada(s) y mostrada(s); "
              "NO se guardó nada (revisa la calidad arriba).")
    else:
        print(f"      {nuevos} artículos nuevos guardados.")
    print("[4/5] Guardado en content/articles.json (archivo histórico).")
    if not PIPELINE_DRY_RUN:
        generar_resumen_dia()  # síntesis del día para la portada (T7)
    print("[5/5] Ejecuta 'python3 generator/build.py' para publicar.")


if __name__ == "__main__":
    main()
