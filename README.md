# Análisis.com — Portal de noticias automatizado

Portal de noticias regional (foco América Latina) **totalmente automatizado**:
redacta artículos originales en español a partir del contraste de múltiples
fuentes internacionales, genera portadas por IA, se actualiza cada 24 h, guarda
todo el histórico y se publica como sitio estático. Estilo editorial (El País /
WSJ). Sin equipo de redacción.

Este README es el punto de entrada. Documentos de apoyo:
`PLAN.md` (arquitectura), `ROADMAP-MEJORAS.md` (estrategia y futuro),
`FUNCIONES.md` (qué está activo / qué requiere claves), `SETUP-IMAGENES.md`
(imágenes por IA).

---

## Arquitectura

Sitio estático generado por Python + automatización con GitHub Actions +
publicación en GitHub Pages. Sin backend ni base de datos. El archivo maestro de
contenido es `content/articles.json`; el sitio se regenera desde ahí.

Flujo diario (orquestado por `.github/workflows/actualizar.yml`):
1. `generator/pipeline.py` — recolecta RSS de fuentes fiables, agrupa la misma
   noticia cubierta por ≥2 medios y **redacta un artículo nuevo** (hook a un LLM).
2. `generator/fetch_data.py` — actualiza `content/data.json` (indicadores).
3. `generator/translate.py` — (opcional) traduce a PT/EN.
4. `generator/build.py` — genera todo el sitio en `site/`.
5. `generator/distribute.py` — publica titulares en Telegram/WhatsApp/email.
6. Commit del histórico + deploy a GitHub Pages.

## Estructura

```
analisis-com/
├── content/
│   ├── articles.json      # ARCHIVO MAESTRO de publicaciones (histórico)
│   ├── data.json          # indicadores del tablero/ticker
│   └── covers/            # portadas cacheadas (png IA / svg), versionadas
├── generator/
│   ├── build.py           # generador del sitio (núcleo, ~900 líneas)
│   ├── images.py          # portadas: OpenAI GPT Image + fallback SVG generativo
│   ├── pipeline.py        # recolección + agrupación + redacción (hook LLM)
│   ├── fetch_data.py      # datos regionales reales (hook APIs)
│   ├── translate.py       # traducción ES→PT/EN (hook OpenAI)
│   ├── distribute.py      # Telegram/WhatsApp/email (hooks)
│   └── sources.json       # fuentes RSS por región y sección
├── site/                  # SITIO GENERADO (salida; no editar a mano)
├── .github/workflows/actualizar.yml
├── requirements.txt       # feedparser, openai, requests
├── README.md  PLAN.md  ROADMAP-MEJORAS.md  FUNCIONES.md  SETUP-IMAGENES.md
```

## Secciones (10)

Tecnología, Economía, Minería, Agricultura, Retail, Banca,
Energía y Medioambiente, Mercados y Cripto, Internacional, Startups.

## Estado actual (al 5 de julio de 2026)

**Funcionando (estático, sin claves):** portal editorial con portadas; 4
artículos de muestra reales; claves en 30 s; escuchar nota (Web Speech);
modo oscuro; tamaño de fuente; tiempo de lectura; barra de progreso; compartir;
relacionadas; búsqueda; asistente "Pregúntale a Análisis" (extractivo);
páginas de tema con línea de tiempo; **ticker de datos en movimiento** bajo el
menú (con monedas en vivo); **cuadro del clima** por geolocalización en portada;
tablero `/datos.html`; boletín diario; personalización "Para ti"; PWA
(offline/instalable); SEO (JSON-LD, sitemaps, robots, RSS).

**Implementado con hook (requiere clave/cuenta):** portadas fotorrealistas
(OpenAI), redacción con IA (Anthropic u otro), datos en vivo de commodities,
traducción PT/EN, Telegram/WhatsApp/email, asistente RAG generativo, analítica,
anuncios. Ver `FUNCIONES.md`.

**Pendiente principal:** desplegar (crear repo GitHub + Pages + DNS a
analisis.com) y conectar las claves. El código nunca se rompe si falta una clave:
degrada con gracia.

## Uso local

```bash
pip install -r requirements.txt
python3 generator/build.py
cd site && python3 -m http.server 8000     # http://localhost:8000
```
Nota: el ticker en vivo, el clima, la búsqueda y el asistente usan `fetch`, así
que conviene verlos con el servidor local o ya desplegado (no por `file://`).

## Variables de entorno / secrets

Ver `FUNCIONES.md` §Variables. Principales: `OPENAI_API_KEY` (imágenes/traducción),
`ANTHROPIC_API_KEY` (redacción), `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`,
`WHATSAPP_TOKEN`/`WHATSAPP_PHONE_ID`, `EMAIL_API_KEY`; variables `ANALYTICS_DOMAIN`,
`ADS`, `SITE_URL`.

## APIs externas usadas (gratis, sin clave)

- Clima: Open-Meteo (`api.open-meteo.com`) + ubicación por IP (`ipwho.is`).
- Monedas en vivo del ticker: `open.er-api.com` (incluye CLP).
- FX del pipeline de datos: `open.er-api.com`.
