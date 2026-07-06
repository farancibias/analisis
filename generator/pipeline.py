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
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content", "articles.json")
SOURCES = os.path.join(ROOT, "generator", "sources.json")

# umbral de similitud de titulares para considerar que dos notas hablan de lo mismo
SIMILARITY = 0.42
# nº mínimo de fuentes distintas que deben cubrir un tema para publicarlo
MIN_SOURCES = 2

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


def agrupar(items):
    """Agrupa entradas que hablan de la misma noticia (por similitud de título)."""
    clusters = []
    for it in items:
        colocado = False
        for c in clusters:
            if _misma_noticia(it, c[0]):
                c.append(it)
                colocado = True
                break
        if not colocado:
            clusters.append([it])
    # sólo temas cubiertos por >=MIN_SOURCES fuentes DISTINTAS
    validos = []
    for c in clusters:
        fuentes = {i["source"] for i in c}
        if len(fuentes) >= MIN_SOURCES:
            validos.append(c)
    return validos


# -------------------------------------------------------------- 3. REDACTAR
SYSTEM_PROMPT = (
    "Eres redactor de Análisis.com, un portal de noticias serio en español "
    "(estilo editorial El País / WSJ). Redactas notas ORIGINALES, informativas "
    "y CONCRETAS en español neutro. Nunca copias ni parafraseas frases de las "
    "fuentes: sintetizas los hechos con tus propias palabras y aportas contexto."
)

REDACCION_PROMPT = """Tienes varios resúmenes de UNA MISMA noticia publicados por distintos medios internacionales.

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
    },
    "required": ["title", "subtitle", "tags", "key_points", "lead", "body",
                 "image_prompt", "image_alt"],
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
        "author": "Redacción Análisis.com",
        "tags": articulo_ia.get("tags", []),
        "image_prompt": articulo_ia.get("image_prompt", ""),
        "image_alt": articulo_ia.get("image_alt") or articulo_ia["title"],
        "key_points": articulo_ia.get("key_points", []),
        "lead": articulo_ia.get("lead") or (body[0] if body else ""),
        "body": body,
        "sources_consulted": sorted({i["source"] for i in cluster}),
    })
    with open(CONTENT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return aid


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
    print("[2/5] Agrupando notas sobre la misma noticia...")
    clusters = agrupar(items)
    print(f"      {len(clusters)} temas con >= {MIN_SOURCES} fuentes.")
    # Modo prueba: quedarse con los temas MEJOR cubiertos (más fuentes distintas).
    if PIPELINE_LIMIT > 0:
        clusters = sorted(
            clusters, key=lambda c: len({i["source"] for i in c}), reverse=True
        )[:PIPELINE_LIMIT]
        print(f"      modo prueba: se procesan {len(clusters)} temas "
              f"(PIPELINE_LIMIT={PIPELINE_LIMIT}).")
    if PIPELINE_DRY_RUN:
        print("      DRY-RUN activo: se mostrarán las notas SIN guardarlas ni publicar.")
    print("[3/5] Redactando artículos originales...")
    nuevos = 0
    for c in clusters:
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
    print("[5/5] Ejecuta 'python3 generator/build.py' para publicar.")


if __name__ == "__main__":
    main()
