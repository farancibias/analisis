#!/usr/bin/env python3
"""
Traducción multilingüe (ES -> PT, EN) con hook a un LLM.
=======================================================
Genera versiones traducidas de los artículos para ampliar alcance regional
(portugués = Brasil) y global (inglés). Se activa con OPENAI_API_KEY; si no,
no hace nada y el sitio queda solo en español.

El generador (build.py) crea etiquetas hreflang cuando existen traducciones.

Uso:  python3 generator/translate.py
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content", "articles.json")
IDIOMAS = {"pt": "portugués de Brasil", "en": "inglés"}


def traducir_texto(texto, idioma):
    """Traduce con un LLM. Devuelve el texto traducido."""
    from openai import OpenAI
    client = OpenAI()
    r = client.chat.completions.create(
        model=os.environ.get("TRANSLATE_MODEL", "gpt-4.1-mini"),
        messages=[{"role": "user",
                   "content": f"Traduce al {idioma}, tono periodístico, "
                              f"sin agregar nada:\n\n{texto}"}],
        temperature=0.2)
    return r.choices[0].message.content.strip()


def traducir_articulo(a, lang_name):
    out = dict(a)
    out["title"] = traducir_texto(a["title"], lang_name)
    out["subtitle"] = traducir_texto(a["subtitle"], lang_name)
    out["body"] = [traducir_texto(p, lang_name) for p in a["body"]]
    if a.get("key_points"):
        out["key_points"] = [traducir_texto(k, lang_name) for k in a["key_points"]]
    return out


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("translate.py: define OPENAI_API_KEY para activar la traducción.")
        return
    with open(CONTENT, encoding="utf-8") as f:
        data = json.load(f)
    for code, name in IDIOMAS.items():
        path = os.path.join(ROOT, "content", f"articles.{code}.json")
        traducidos = []
        for a in data["articles"]:
            print(f"  {code}: {a['id']}")
            traducidos.append(traducir_articulo(a, name))
        salida = dict(data, articles=traducidos)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=2)
        print(f"  -> {path}")


if __name__ == "__main__":
    main()
