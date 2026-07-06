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
from datetime import datetime, timezone
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content", "articles.json")
SOURCES = os.path.join(ROOT, "generator", "sources.json")

# umbral de similitud para considerar que dos notas hablan de lo mismo
SIMILARITY = 0.42
# nº mínimo de fuentes distintas que deben cubrir un tema para publicarlo
MIN_SOURCES = 2


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


def _similar(a, b):
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def agrupar(items):
    """Agrupa entradas que hablan de la misma noticia (por similitud de título)."""
    clusters = []
    for it in items:
        colocado = False
        for c in clusters:
            if _similar(it["title"], c[0]["title"]) >= SIMILARITY:
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
REDACCION_PROMPT = """Eres redactor de Análisis.com, un portal de noticias serio en español.
A continuación tienes varios resúmenes de una MISMA noticia publicados por
distintos medios internacionales. Tu tarea:

1. Verifica qué hechos aparecen confirmados por 2 o más fuentes.
2. Escribe un artículo COMPLETAMENTE ORIGINAL en español neutro.
   - NO copies ni parafrasees frases; redacta desde cero.
   - NO inventes datos: usa sólo hechos presentes en los resúmenes.
   - Atribuye declaraciones o cifras exclusivas ("según X").
   - Tono informativo, contextualizado, sin opinión.
3. Devuelve JSON con: title, subtitle, tags (3), body (5-6 párrafos).

RESÚMENES DE LAS FUENTES:
{fuentes}
"""


def redactar(cluster):
    """
    Escribe un artículo original a partir del cluster de fuentes.

    >>> AQUÍ SE CONECTA EL MODELO DE IA <<<
    Ejemplo con la API de Anthropic (pseudocódigo):

        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        fuentes = "\\n\\n".join(f"[{i['source']}] {i['title']}\\n{i['summary']}"
                                for i in cluster)
        msg = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1500,
            messages=[{"role": "user",
                       "content": REDACCION_PROMPT.format(fuentes=fuentes)}],
        )
        data = json.loads(msg.content[0].text)

    El bloque de abajo es un marcador de posición para poder ejecutar el
    pipeline de punta a punta sin clave de API.
    """
    base = cluster[0]
    return {
        "title": base["title"][:110],
        "subtitle": "Síntesis original a partir de múltiples fuentes.",
        "tags": [base.get("section_hint") or "Actualidad"],
        "image_prompt": f"Ilustración editorial sobre {base['title'][:70]}, sin texto",
        "body": [
            "[Borrador automático] Este párrafo sería redactado por el modelo de "
            "IA a partir del contraste de las fuentes del cluster.",
            f"Fuentes que cubren el tema: "
            f"{', '.join(sorted({i['source'] for i in cluster}))}.",
        ],
    }


# ---------------------------------------------------------------- 4. GUARDAR
def guardar(articulo_ia, section):
    with open(CONTENT, encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-",
                  articulo_ia["title"].lower())[:60].strip("-")
    aid = f"{today}-{slug}-{hashlib.md5(articulo_ia['title'].encode()).hexdigest()[:6]}"
    if any(a["id"] == aid for a in data["articles"]):
        return None  # ya existe: evita duplicados
    data["articles"].append({
        "id": aid,
        "section": section,
        "title": articulo_ia["title"],
        "subtitle": articulo_ia["subtitle"],
        "date": today,
        "author": "Redacción Análisis.com",
        "tags": articulo_ia.get("tags", []),
        "image_prompt": articulo_ia.get("image_prompt", ""),
        "image_alt": articulo_ia["title"],
        "lead": articulo_ia["body"][0],
        "body": articulo_ia["body"],
        "sources_consulted": [],
    })
    with open(CONTENT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return aid


# -------------------------------------------------------------------- MAIN
def main():
    # Guarda: no publicar borradores automáticos hasta conectar el modelo de
    # redacción. Mientras no exista la clave, el pipeline no toca articles.json
    # (el sitio se publica solo con el contenido curado existente).
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("PIPELINE_LLM")):
        print("pipeline: sin ANTHROPIC_API_KEY -> no se generan artículos "
              "automáticos (se conserva el contenido actual). Conecta el modelo "
              "en redactar() para activar la redacción.")
        return
    with open(SOURCES, encoding="utf-8") as f:
        sources = json.load(f)["feeds"]
    print(f"[1/5] Recolectando de {len(sources)} fuentes...")
    items = recolectar(sources)
    print(f"      {len(items)} entradas descargadas.")
    print("[2/5] Agrupando notas sobre la misma noticia...")
    clusters = agrupar(items)
    print(f"      {len(clusters)} temas con >= {MIN_SOURCES} fuentes.")
    print("[3/5] Redactando artículos originales...")
    nuevos = 0
    for c in clusters:
        art = redactar(c)
        section = c[0].get("section_hint") or "internacional"
        if guardar(art, section):
            nuevos += 1
    print(f"      {nuevos} artículos nuevos guardados.")
    print("[4/5] Guardado en content/articles.json (archivo histórico).")
    print("[5/5] Ejecuta 'python3 generator/build.py' para publicar.")


if __name__ == "__main__":
    main()
