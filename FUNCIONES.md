# Análisis.com — Funciones implementadas

Se implementó todo el roadmap. Esta guía indica **qué funciona ya** (sin
configurar nada) y **qué requiere una clave o cuenta tuya** para activarse.
Todo tiene respaldo: si una integración externa no está configurada, el sitio
no se rompe.

## ✅ Funciona ya (100% estático, sin claves)

| Función | Dónde |
|---------|-------|
| **Claves en 30 segundos** (resumen de cada nota) | en cada artículo |
| **Escuchar la nota** (voz del navegador, Web Speech API, gratis) | botón ▶ Escuchar |
| **Modo oscuro / claro** y **tamaño de fuente** | barra superior (◐, A-, A+) |
| **Tiempo de lectura** y **barra de progreso** | artículos |
| **Compartir** (nativo + copiar enlace) | botón Compartir |
| **Buscar** en todo el archivo | `/buscar.html` |
| **Pregúntale a Análisis** (responde con tus artículos) | `/asistente.html` |
| **Páginas de tema con línea de tiempo** | `/tema/<tema>.html` (desde los tags) |
| **Relacionadas** al final de cada nota | artículos |
| **Franja (ticker) de datos en movimiento** bajo el menú, en todas las páginas; monedas en vivo | global |
| **Cuadro del clima** (estado + pronóstico 3 días) según ubicación del visitante | portada |
| **Tablero de datos regionales** (commodities, monedas, tasas), funciona también sin servidor | `/datos.html` |
| **Boletín diario** (edición y página de alta) | `/boletin/` |
| **Personalización "Para ti"** (seguir secciones, reordena la portada) | botón «Seguir» |
| **PWA**: instalable y con modo offline | `manifest` + `sw.js` |
| **SEO**: JSON-LD NewsArticle, Open Graph, `sitemap.xml`, news sitemap, `robots.txt`, `rss.xml` | automático |
| **Accesibilidad** (contraste, tipografía, texto alternativo) | global |

## 🔌 Requiere tu clave/cuenta (ya implementado con enganche)

| Función | Qué necesitas | Cómo se activa |
|---------|---------------|----------------|
| **Portadas fotorrealistas** | `OPENAI_API_KEY` | ver `SETUP-IMAGENES.md` |
| **Redacción automática con IA** | `ANTHROPIC_API_KEY` (o el modelo que uses) | `generator/pipeline.py` |
| **Datos en vivo** (precios reales) | API de metales/commodities (monedas ya funcionan sin clave) | `generator/fetch_data.py` |
| **Traducción PT/EN** | `OPENAI_API_KEY` | `generator/translate.py` (genera `articles.pt.json`, `articles.en.json`) |
| **Canal de WhatsApp** | WhatsApp Cloud API (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`) | `generator/distribute.py` |
| **Canal de Telegram** | Bot token (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) | `generator/distribute.py` (ya funcional) |
| **Envío del boletín por email** | proveedor transaccional (`EMAIL_API_KEY`) | `generator/distribute.py` |
| **Asistente con respuestas redactadas (RAG generativo)** | un endpoint LLM | define `window.ANALISIS_ASK_URL` en el sitio |
| **Analítica** (Plausible) | tu dominio | variable `ANALYTICS_DOMAIN` |
| **Anuncios** | tu red publicitaria | variable `ADS=1` muestra los slots |

## Variables de entorno (resumen)

Secrets (Settings → Secrets and variables → Actions → *Secrets*):
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `EMAIL_API_KEY`.

Variables (pestaña *Variables*): `ANALYTICS_DOMAIN`, `ADS`.

El workflow `.github/workflows/actualizar.yml` ya orquesta todo el flujo diario:
recolectar → traducir (opcional) → datos → generar sitio → distribuir → publicar.

## Probar en local

```bash
pip install feedparser openai requests
python3 generator/build.py
cd site && python3 -m http.server 8000   # abre http://localhost:8000
```

## El asistente "Pregúntale a Análisis"

Por defecto responde de forma **extractiva**: recupera y muestra los artículos
más relevantes del archivo (sin costo, sin backend). Para respuestas **redactadas**
por un modelo (RAG generativo), publica un pequeño endpoint que reciba `{q}` y
devuelva `{answer}`, y en el sitio define:

```html
<script>window.ANALISIS_ASK_URL = "https://tu-endpoint/ask";</script>
```

## Notas

- **Prioridad de despliegue sugerida:** primero lo que ya funciona (no requiere
  nada). Luego conecta OpenAI (imágenes + traducción), Telegram (rápido y gratis)
  y una API de datos. WhatsApp y email al final, porque requieren aprobación de
  plantillas / cuenta de envío.
- **Costo:** lo único con costo por uso es OpenAI (imágenes y traducción). El
  resto es gratis o de bajo costo. Ver estimación en `SETUP-IMAGENES.md`.
