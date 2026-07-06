#!/usr/bin/env python3
"""
Generador de portadas para Análisis.com — SIN COSTO Y SIN DERECHOS.
==================================================================
Produce una ilustración de portada (SVG 16:9) única para cada artículo,
determinística a partir de un 'seed' (el id del artículo) y con paleta y
motivo según la sección. Al ser generadas por código, no hay licencias
ni derechos de terceros: son 100% propias.

Uso:
    from images import cover_svg
    svg = cover_svg(seed="2026-07-05-...", section="mineria")

Para portadas FOTORREALISTAS con un modelo de IA, ver el hook
`generar_imagen_ia()` al final de este archivo.
"""

import base64
import hashlib
import os
import random

# Paleta por sección: (color oscuro, color medio, acento claro)
PALETTES = {
    "tecnologia":    ("#0a2a66", "#1e6fd6", "#63e6ff"),
    "economia":      ("#0b3d2e", "#1b7a4b", "#8ee6b0"),
    "mineria":       ("#5a2e0c", "#b5651d", "#f2b45c"),
    "agricultura":   ("#38460c", "#7a9a1c", "#e6d24a"),
    "retail":        ("#4a0d3d", "#a3238e", "#ff8ad1"),
    "banca":         ("#0d1b3d", "#2a4785", "#7aa0e6"),
    "energia":       ("#5a1a0c", "#d1521d", "#f5c24a"),
    "mercados":      ("#1a0d4a", "#4b3fa3", "#c9b8ff"),
    "internacional": ("#4a0d10", "#b52330", "#ff9aa0"),
    "startups":      ("#2e0d4a", "#7a2fb5", "#d79aff"),
}

# Motivo gráfico por sección
MOTIF = {
    "tecnologia": "network", "startups": "network",
    "economia": "bars", "mercados": "bars", "banca": "bars", "retail": "bars",
    "mineria": "facets", "energia": "facets",
    "agricultura": "rings", "internacional": "rings",
}

W, H = 1200, 675


def _rng(seed):
    n = int(hashlib.md5(str(seed).encode()).hexdigest(), 16)
    return random.Random(n)


def _bars(r, acc):
    out, x = [], 120
    while x < W - 80:
        h = r.randint(90, 430)
        op = r.choice([0.85, 0.6, 0.4, 0.9])
        col = r.choice([acc, "#ffffff", acc])
        out.append(f'<rect x="{x}" y="{H-70-h}" width="58" height="{h}" '
                   f'rx="3" fill="{col}" opacity="{op}"/>')
        x += r.randint(74, 96)
    return "".join(out)


def _network(r, acc):
    nodes = [(r.randint(140, W-140), r.randint(120, H-120)) for _ in range(8)]
    out = []
    for i, (x, y) in enumerate(nodes):
        for (x2, y2) in nodes[i+1:]:
            if abs(x-x2) + abs(y-y2) < 520:
                out.append(f'<line x1="{x}" y1="{y}" x2="{x2}" y2="{y2}" '
                           f'stroke="#ffffff" stroke-width="1.4" opacity="0.35"/>')
    for (x, y) in nodes:
        rad = r.randint(9, 26)
        out.append(f'<circle cx="{x}" cy="{y}" r="{rad}" fill="{acc}" opacity="0.95"/>')
        out.append(f'<circle cx="{x}" cy="{y}" r="{rad+12}" fill="none" '
                   f'stroke="{acc}" stroke-width="1.2" opacity="0.4"/>')
    return "".join(out)


def _facets(r, acc):
    out = []
    for _ in range(7):
        cx, cy = r.randint(150, W-150), r.randint(140, H-140)
        s = r.randint(70, 180)
        pts = []
        sides = r.choice([3, 6])
        rot = r.random() * 6.28
        import math
        for k in range(sides):
            a = rot + k * 6.283 / sides
            pts.append(f"{int(cx + s*math.cos(a))},{int(cy + s*math.sin(a))}")
        op = r.choice([0.16, 0.24, 0.32])
        out.append(f'<polygon points="{" ".join(pts)}" fill="{acc}" opacity="{op}" '
                   f'stroke="#ffffff" stroke-width="1.1" stroke-opacity="0.4"/>')
    return "".join(out)


def _rings(r, acc):
    out = []
    cx, cy = r.randint(W-320, W-120), r.randint(160, H-160)
    for rad in range(60, 520, 46):
        op = max(0.08, 0.5 - rad / 1100)
        col = acc if (rad // 46) % 2 == 0 else "#ffffff"
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{rad}" fill="none" '
                   f'stroke="{col}" stroke-width="{r.choice([2,3,5])}" opacity="{op:.2f}"/>')
    return "".join(out)


_MOTIF_FN = {"bars": _bars, "network": _network, "facets": _facets, "rings": _rings}


def cover_svg(seed, section):
    r = _rng(seed)
    c1, c2, acc = PALETTES.get(section, ("#1a1a1a", "#444", "#ddd"))
    gid = f"g{abs(hash(seed)) % 99999}"
    ang = r.choice([0, 20, 35, 55])

    # círculos translúcidos de fondo (profundidad)
    blobs = []
    for _ in range(3):
        cx, cy = r.randint(-80, W+80), r.randint(-80, H+80)
        rad = r.randint(200, 460)
        col = r.choice(["#ffffff", acc])
        blobs.append(f'<circle cx="{cx}" cy="{cy}" r="{rad}" fill="{col}" opacity="0.07"/>')

    motif = _MOTIF_FN[MOTIF.get(section, "rings")](r, acc)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img">
<defs>
  <linearGradient id="{gid}" gradientTransform="rotate({ang})">
    <stop offset="0" stop-color="{c1}"/>
    <stop offset="1" stop-color="{c2}"/>
  </linearGradient>
  <radialGradient id="{gid}v" cx="50%" cy="42%" r="75%">
    <stop offset="60%" stop-color="#000000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000000" stop-opacity="0.35"/>
  </radialGradient>
  <filter id="{gid}n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/>
    <feColorMatrix type="saturate" values="0"/></filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#{gid})"/>
{"".join(blobs)}
{motif}
<rect width="{W}" height="{H}" fill="url(#{gid}v)"/>
<rect width="{W}" height="{H}" filter="url(#{gid}n)" opacity="0.05"/>
</svg>'''


# ==========================================================================
# PORTADAS FOTORREALISTAS CON OPENAI GPT IMAGE
# ==========================================================================
# Se activa automáticamente si existe la variable de entorno OPENAI_API_KEY.
# Si no existe, o si la llamada falla, el sitio cae de vuelta en la portada
# ilustrada SVG (sin costo, sin derechos). Cada portada PNG se cachea: no se
# vuelve a generar (ni a cobrar) si el archivo ya existe.
#
#   Modelo:   gpt-image-1.5 (por defecto; configurable con IMAGE_MODEL)
#   Calidad:  "medium" = equilibrio (configurable con IMAGE_QUALITY:
#                                     low | medium | high)
#   Tamaño:   1536x1024 (3:2 apaisado; configurable con IMAGE_SIZE)
#
# Requisito:  pip install openai
# --------------------------------------------------------------------------
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-1.5")
IMAGE_QUALITY = os.environ.get("IMAGE_QUALITY", "medium")
IMAGE_SIZE = os.environ.get("IMAGE_SIZE", "1536x1024")

ESTILO = ("Fotografía editorial periodística, fotorrealista, luz natural, "
          "gran nitidez, composición horizontal, sin ningún texto ni letras, "
          "sin logotipos, sin marcas de agua.")


def generar_imagen_ia(prompt):
    """Genera una portada fotorrealista con OpenAI y devuelve los bytes PNG.
    Lanza excepción si falla (el llamador hace fallback a SVG)."""
    from openai import OpenAI  # import diferido: sólo si se usa
    client = OpenAI()  # lee OPENAI_API_KEY del entorno
    resp = client.images.generate(
        model=IMAGE_MODEL,
        prompt=f"{prompt}. {ESTILO}",
        size=IMAGE_SIZE,
        quality=IMAGE_QUALITY,
        n=1,
    )
    return base64.b64decode(resp.data[0].b64_json)


def build_cover(seed, section, prompt, imgdir, basename):
    """Escribe la portada del artículo y devuelve el nombre de archivo usado.

    Prioridad:
      1. Si ya existe un PNG cacheado -> se reutiliza (no se vuelve a cobrar).
      2. Si hay OPENAI_API_KEY y un prompt -> genera PNG fotorrealista.
      3. En cualquier otro caso o ante un error -> ilustración SVG.
    """
    png_name, png_path = basename + ".png", os.path.join(imgdir, basename + ".png")
    if os.path.exists(png_path):
        return png_name
    if os.environ.get("OPENAI_API_KEY") and prompt:
        try:
            data = generar_imagen_ia(prompt)
            with open(png_path, "wb") as f:
                f.write(data)
            print(f"  imagen IA generada: {png_name}")
            return png_name
        except Exception as e:  # noqa: BLE001
            print(f"  aviso: falló la imagen IA ({e}); uso portada SVG.")
    svg_name = basename + ".svg"
    with open(os.path.join(imgdir, svg_name), "w", encoding="utf-8") as f:
        f.write(cover_svg(seed, section))
    return svg_name
