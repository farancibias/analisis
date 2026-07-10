# Backlog priorizado para Claude Code — mejoras de analisis.com

Basado en la revisión del sitio en vivo (`REVISION-SITIO.md`). Tareas ordenadas
por prioridad, con archivos, cambios concretos y criterios de aceptación.

> **Estado de ejecución (2026-07-06):** ✅ HECHAS y en vivo — **T1–T5, T7–T9, T11,
> T12, T15**, además de **reacciones/encuesta** al pie y **multi-idioma ES/EN/PT/DE**
> (botón + auto por país + traducción IA vía Worker). Commit por tarea, verificadas
> en producción. ⏳ Pendientes — **T6** (Mi Análisis/Login), **T10** (pre-generar
> páginas por idioma con hreflang; el multi-idioma actual es cliente/on-demand),
> **T13** (formatos), **T14** (monetización).
>
> Infra añadida: sitio tras **Cloudflare** (HTTPS + caché), **Worker** `analisis-ask`
> con `/api/ask` (asistente) y `/api/translate` (idiomas) — ver `worker/README.md`.
> Assets versionados (`app.js?v=hash`) para bustar la caché del edge.

## Cómo trabajar (para Code)
- Antes de empezar lee: `ESTADO.md`, `REVISION-SITIO.md`, y el código actual de
  `generator/pipeline.py`, `generator/images.py`, `generator/build.py` y
  `generator/sources.json` (algunos han cambiado desde el diseño inicial: ya hay
  integración con Pexels, Login y `panel.html`).
- Reglas: el sitio es estático; toda integración externa debe **degradar con
  gracia** si falta la clave; respeta la caché de portadas (`content/covers/`);
  los artículos son **redacción propia** (no copiar frases), verificar con ≥2
  fuentes, atribuir datos exclusivos.
- Definición de "hecho" por tarea: `python3 generator/build.py` corre sin error,
  sírvelo en local (`cd site && python3 -m http.server 8000`) y verifica en el
  navegador las páginas afectadas. Haz commit por tarea.

---

# P0 — Calidad editorial (resolver ANTES de empujar tráfico)

## T1 · Arreglar la relevancia de las imágenes  ⭐ máxima prioridad
**Problema:** la nota líder de hoy ($TRUMP) salió con una foto de una protesta
BLM con un insulto a Trump. El match de Pexels es muy laxo y arriesgado.
**Archivos:** `generator/images.py`, `generator/pipeline.py`.
**Cambios:**
- Construir la query de imagen desde **entidades/tema** de la nota (sección +
  tags + sustantivos clave), no desde el titular completo.
- **Umbral de pertinencia:** si la mejor foto no supera el umbral (o no hay
  resultados claros), usar la **portada ilustrada SVG** existente como fallback.
- **Lista negra** de términos/resultados sensibles (protest, riot, flag,
  political rally, caras identificables) salvo que la nota lo requiera.
- Guardar en cada artículo el **crédito real** (Pexels + autor / ilustración /
  IA) y mostrarlo en el `figcaption`.
- Mantener la caché: no re-descargar si ya existe portada.
**Aceptación:** ninguna nota muestra fotos de protestas/políticas sin relación;
las notas sin buena foto usan ilustración; el crédito refleja el origen real.

## T2 · Foco regional (América Latina)
**Problema:** la portada la dominan Guardian/BBC (tuberculosis bovina en Cumbria,
Sky/ITV, Starling Bank, Wegovy NHS). Se siente británica, no latinoamericana.
**Archivos:** `generator/sources.json`, `generator/pipeline.py`.
**Cambios:**
- **Añadir fuentes regionales en español** (verificar que el RSS esté vivo):
  Bloomberg Línea, América Economía, Infobae, La Tercera / Emol / BioBioChile (CL),
  El Financiero / Expansión (MX), Valor Econômico / Folha (BR), El Comercio (PE),
  La Nación / Ámbito (AR), El Tiempo / Portafolio (CO), EFE/Reuters LatAm.
- **Puntaje de relevancia regional** por artículo: +peso si menciona países,
  empresas, monedas o mercados de la región; usarlo para **ordenar la portada**.
- **Filtro de no-noticias:** descartar "cartas al director", opinión, live-blogs,
  obituarios/sucesos locales irrelevantes (por título/sección/patrones).
**Aceptación:** en una corrida nueva, la portada prioriza notas regionales y
desaparecen las piezas hiperlocales británicas y las "cartas al director".

## T3 · Selección de líder por importancia + deduplicación
**Problema:** la líder es la primera nota (hoy, cripto de 1 min) y hay temas
repetidos (dos notas de cobre/litio el mismo día).
**Archivos:** `generator/pipeline.py`, `generator/build.py` (`_home`).
**Cambios:**
- Calcular un **score de importancia** (sección prioritaria + nº de fuentes del
  cluster + relevancia regional + recencia) y elegir la líder por ese score.
- **Deduplicar** por similitud de tema el mismo día (reforzar el agrupado que ya
  existe en `agrupar()`), y evitar dos notas casi iguales en portada.
**Aceptación:** la líder es una nota relevante y contrastada; no hay pares casi
idénticos en la portada.

## T4 · Señales de confianza visibles
**Archivos:** `generator/build.py` (plantilla de artículo), `pipeline.py`.
**Cambios:** en cada nota mostrar fecha/hora de actualización, **nº de fuentes
contrastadas**, y enlace a una **política de correcciones** (página nueva simple).
**Aceptación:** cada artículo muestra esas señales; existe `/correcciones.html`.

---

# P1 — Funcionalidades de alto valor

## T5 · Portada priorizada por el país del lector
Ya se detecta la ubicación por IP para el clima. Reutilizarla para **subir en la
portada las noticias del país del lector** y ofrecer un selector de país
(persistir en localStorage).
**Archivos:** `generator/build.py` (JS de portada + `search-index.json` con
campo país), `pipeline.py` (etiquetar país por nota).
**Aceptación:** un lector en Chile ve primero notas de Chile; puede cambiar el país.

## T6 · "Mi Análisis" (aprovechar el Login existente)
Seguir temas/secciones, **guardar/leer después**, y boletín personalizado.
**Archivos:** front (JS + páginas nuevas) y, si hay backend de login, su API.
**Aceptación:** un usuario logueado guarda notas y ve su lista "Leer después".

## T7 · Resumen del día en portada
Bloque "Las 5 claves de hoy" generado automáticamente arriba de la portada.
**Archivos:** `generator/pipeline.py` (genera resumen del día), `build.py` (`_home`).
**Aceptación:** la portada muestra un resumen diario con enlaces a las notas fuente.

## T8 · Audio briefing + activar boletín y mensajería
Voz IA de calidad para "Escuchar" y un **podcast diario** (3–5 min) del resumen;
activar `distribute.py` (Telegram funcional; WhatsApp/email con cuenta).
**Archivos:** `generator/distribute.py`, `build.py`, hook TTS en `images.py`/nuevo
`audio.py`.
**Aceptación:** existe un audio del día; los titulares se publican en Telegram si
hay token; el boletín se envía si hay proveedor.

## T9 · Hubs por país y por empresa
Extender las páginas de tema a **hubs de país** (Chile, Brasil, México…) y de
**empresa/entidad** (Codelco, Vale, Petrobras) con su línea de tiempo.
**Archivos:** `generator/build.py` (`_temas` → añadir país/empresa; NER simple en
`pipeline.py`).
**Aceptación:** existen `/pais/<slug>.html` y `/empresa/<slug>.html` enlazados.

## T10 · Traducción PT/EN en producción
Activar `generator/translate.py`, generar variantes y añadir `hreflang`.
**Aceptación:** cada nota tiene versión PT y EN accesible; hreflang correcto.

## T11 · Widgets de datos interactivos
Conversor de divisas y calculadora de commodities en `/datos.html`; **mini-gráfico
embebido** del indicador relacionado dentro de las notas de esa sección.
**Archivos:** `generator/build.py` (JS de datos + inserción en artículo).
**Aceptación:** una nota de minería muestra el gráfico del cobre; el conversor
funciona.

## T12 · Optimización para respuestas de IA (AEO) + SEO
Reforzar schema (`NewsArticle`, `FAQPage` cuando aplique), datos estructurados y
un resumen citable por nota para aparecer en respuestas de chatbots.
**Aceptación:** validación de datos estructurados sin errores; cada nota expone
un resumen y FAQ estructurados cuando corresponde.

---

# P2 — Formatos y monetización (cuando haya audiencia)

## T13 · Formatos de contenido
Explicadores y "en profundidad"; **glosario económico** enlazado; **rankings/listas**
automatizados con datos; **newsletters temáticas** por sección; **tarjetas para
redes** (imagen-resumen por nota); **encuestas/reacciones** al pie.

## T14 · Monetización
Suscripción/membresía (sin anuncios, premium, alertas); **API de datos y reportes
B2B**; publicidad contextual por sección.

---

## T15 · "Pregúntale a Análisis" como barra principal (interna + web)  ⭐ NUEVA prioridad P1
Barra prominente en la portada, **sobre "Las 5 claves de hoy"**, que responde
cualquier pregunta elaborando la respuesta con información **interna + web** (vía
backend serverless), **cita fuentes externas** y **lista artículos de Análisis
relacionados** clicables. Requiere un endpoint `/ask` (no se puede en cliente puro).
**Spec completa, arquitectura, seguridad y prompt:** ver **`TAREA-ASISTENTE.md`**.
**Archivos:** nuevo backend `api/ask`; `generator/build.py` (`_home`, `ASK_JS`,
`asistente.html`). **Degrada** al modo interno si no hay backend.

---

## Orden sugerido de ejecución
Pendientes: **T15** (asistente barra principal) → T6 (Mi Análisis/Login) → T10
(traducción PT/EN) → P2. (T1–T5, T7–T9, T11–T12 ya hechas y en vivo.)
Haz T15 pronto: es lo que Felipe quiere priorizar ahora.
