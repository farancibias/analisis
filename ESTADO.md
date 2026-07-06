# Análisis.com — Estado actual y traspaso

**Última actualización:** 2026-07-06 · **En vivo:** https://analisis.com
**Repo:** github.com/farancibias/analisis (público) · **Cuenta GitHub:** `farancibias` (gh autenticado)

Portal de noticias regional (foco LatAm) **automatizado**, sitio **estático** generado con
Python + GitHub Actions + GitHub Pages. Sin backend. Estilo editorial (El País / WSJ).
Documentos de apoyo: `README.md`, `PLAN.md`, `FUNCIONES.md`, `DESPLIEGUE.md`,
`ROADMAP-MEJORAS.md`, `SETUP-IMAGENES.md`. Este archivo (`ESTADO.md`) es el resumen vivo.

---

## 1. Qué está ACTIVO ahora (con claves conectadas)

| Función | Estado | Clave/secret |
|---|---|---|
| **Sitio publicado** en https://analisis.com (dominio propio, HTTPS) | ✅ En vivo | — |
| **Redacción automática con Claude** (pipeline) | ✅ Activo | `ANTHROPIC_API_KEY` |
| **Fotos reales de portada** (Pexels, por tags) | ✅ Activo | `PEXELS_API_KEY` |
| **Panel privado de analítica** `/panel.html` | ⚙️ Listo, falta conectar GA4 | (GA4_* pendientes) |
| Portadas IA (OpenAI), traducción PT/EN, TTS, Telegram/WhatsApp/email | 🔌 Hooks, sin clave | varias |

## 2. Pipeline de redacción (`generator/pipeline.py`)

- **Corre solo en el cron diario 09:00 UTC** (06:00 CL/AR) y en *Run workflow* manual.
  **NO** se dispara en pushes de código (`if: github.event_name != 'push'` en el workflow).
- **Genera 2 notas por cada una de las 10 secciones** (~20/día). Configurable con la var
  `PIPELINE_PER_SECTION` (def. 2). Modelo por defecto `claude-opus-4-8` (var `PIPELINE_MODEL`
  para cambiarlo, p.ej. `claude-sonnet-5` = más barato).
- Flujo: **27 fuentes RSS verificadas** (`generator/sources.json`, cada sección con ≥2 fuentes)
  → selección por sección (prioriza temas con ≥2 fuentes, completa con fuente única)
  → **Claude redacta** (structured outputs, ~300 palabras, concreto, con nombres/cifras)
  → guarda en `content/articles.json` → build → deploy.
- Robusto: si un feed muere o la IA falla en un tema, se omite; el build/deploy nunca se cae.
- **Modo prueba** (opcional, vars del repo): `PIPELINE_DRY_RUN=1` (genera y muestra en el log
  sin publicar) y `PIPELINE_LIMIT=N` (tope global). Hoy **no** están puestas (ciclo completo).
- Costo: ~US$1–1,5/día con Opus 4.8 (~20 notas). Con Sonnet 5, ~la mitad.

## 3. Panel privado de analítica (`/panel.html`)

- Página con **contraseña** (hash SHA-256 en cliente; ofuscación, no cifrado) + `noindex` +
  robots `Disallow`. No enlazada en el menú, pero hay un **botón "LogIn"** en la barra superior
  de la portada (al lado de Buscar) que lleva ahí.
- Muestra: KPIs (sesiones, únicos, vistas, % recurrentes), **ranking por sección**, **países**,
  **nuevos vs recurrentes**, y **"focos sugeridos"** (inteligencia: mayor interés / menor tracción /
  fidelización, calculada en el cliente).
- Datos: `generator/analytics.py` consulta la **GA4 Data API** en el build (clave en secrets,
  nunca en el navegador) → `content/analytics.json`. Sin GA4 muestra "conecta GA4".
- **Para activarlo** (pendiente del usuario): crear propiedad GA4 + cuenta de servicio Google
  Cloud (Analytics Data API, Viewer en la propiedad) y cargar:
  - Variable `GA4_ID` (Measurement ID G-XXXX, para el tracking)
  - Secret `GA4_PROPERTY_ID` (id numérico)
  - Secret `GA4_CREDENTIALS` (JSON de la cuenta de servicio)
  - Secret `PANEL_PASSWORD` (clave del panel; por defecto `analisis`)

## 4. Secrets y variables del repo

**Secrets configurados:** `ANTHROPIC_API_KEY`, `PEXELS_API_KEY`.
**Pendientes (opcionales):** `GA4_PROPERTY_ID`, `GA4_CREDENTIALS`, `PANEL_PASSWORD`,
`OPENAI_API_KEY`, `TELEGRAM_*`, `WHATSAPP_*`, `EMAIL_API_KEY`.
**Variables:** ninguna puesta hoy. Opcionales: `GA4_ID`, `PIPELINE_MODEL`, `PIPELINE_PER_SECTION`,
`PIPELINE_DRY_RUN`, `PIPELINE_LIMIT`, `AUDIO_TTS`, `TTS_VOICE`, `ANALYTICS_DOMAIN`, `ADS`.

## 5. Cambios recientes de UI

- **Botón "LogIn"** en la barra superior (→ `/panel.html`).
- **Zoom A-/A+ arreglado**: el CSS usa px (no rem), así que ahora escalan el contenido con
  `zoom` (0.85×–1.4×) y persiste en localStorage.
- Logo de marca (símbolo animado de anillos + wordmark) en cabecera y footer; favicon a color.
- "Lo último" en portada limitado a 3 con scroll.

## 6. Problemas conocidos / operación

- **Certificado del apex intermitente**: el cert gestionado de GitHub estuvo/está en estado
  `new` (re-emitiéndose). Consecuencia: los **deploys de Pages fallan de forma intermitente**
  ("Deployment failed, try again later") y, en un caso, un deploy marcó "success" pero sirvió
  contenido viejo. **El contenido nunca se pierde** (el bot lo commitea antes de desplegar).
  - **Si el cron genera notas pero no aparecen en vivo:** lanzar *Actions → Run workflow*
    (o `git commit --allow-empty && git push`) para forzar un deploy fresco.
  - Se intentó destrabar el cert quitando/reagregando el custom domain; si sigue en `new`,
    esperar a que GitHub apruebe o abrir ticket a soporte de Pages. `Enforce HTTPS` se activa
    cuando el cert quede `approved` (el sitio ya sirve HTTPS igual).
- **Probar en local:** `pip install -r requirements.txt && python3 generator/build.py &&
  cd site && python3 -m http.server 8000`. El SW cachea; para ver cambios, desregistrar SW +
  limpiar caché o hard-reload.

## 7. Pendientes accionables

1. **Rotar `ANTHROPIC_API_KEY`** en console.anthropic.com (se pegó en el chat). Luego
   `gh secret set ANTHROPIC_API_KEY` con la nueva.
2. **Activar GA4** para llenar el panel (ver §3).
3. **Estabilizar el certificado** del apex (§6) para que los deploys diarios dejen de necesitar
   empujones.
4. (Opcional) Afinar `sources_consulted`/clustering para quitar fuentes de sección ajena;
   cifrar el blob del panel para privacidad real; insight del panel con Claude.
