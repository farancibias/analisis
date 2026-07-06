# T15 · "Pregúntale a Análisis" como barra principal con respuesta IA (interna + web)

Especificación para Claude Code. Es la **nueva prioridad P1** pedida por Felipe.

## Objetivo
Convertir "Pregúntale a Análisis" en el elemento central de la portada: una
**barra prominente** donde el lector escribe **cualquier pregunta** y el sistema
**elabora una respuesta** buscando información **dentro y fuera del sitio**
(buscadores / páginas de terceros). La respuesta debe además **listar los
artículos de Análisis relacionados** con el tema, clicables.

## Ubicación y UX
- Colocar la barra **bajo el ticker de datos y ARRIBA de "Las 5 claves de hoy"**
  en la portada. Mantener también la página `/asistente.html` (versión completa).
- Componentes: input grande + botón "Preguntar" + 3–4 chips de ejemplo
  ("¿Cómo va el cobre?", "¿Qué pasa con las tasas en la región?", …).
- Al enviar, el **panel de respuesta se expande en línea** (sin recargar), con
  estados: cargando → respuesta → error. La respuesta tiene tres partes:
  1. **Texto elaborado** (síntesis original en español).
  2. **Fuentes** externas citadas, con enlace (dominio + título).
  3. **"En Análisis.com" → artículos relacionados** como tarjetas clicables.
- Guardar un historial breve de la sesión (opcional, localStorage).

## Arquitectura (IMPORTANTE: requiere backend serverless)
El sitio es estático; **no** se puede buscar en la web ni llamar a un LLM desde el
navegador (expondría claves y no hay forma de facturarlo). Se necesita un
**endpoint serverless** (Cloudflare Workers / Vercel / Netlify Functions).

**Contrato del endpoint** `POST /ask` con body `{ "q": "<pregunta>" }` →
```json
{
  "answer": "texto elaborado en español...",
  "sources": [ { "title": "...", "url": "https://..." } ],
  "related": [ { "title":"...", "url":"/articulo/....html", "section":"...", "date":"..." } ]
}
```
**Flujo del endpoint:**
1. **Recuperar artículos internos** relacionados: leer `search-index.json`
   (ya existe) o, mejor, un índice de **embeddings** del archivo → top 3–5.
2. **Búsqueda web:** llamar a un search API (opciones: Brave Search API, Tavily,
   Bing, SerpAPI) → top resultados con título, url y snippet.
3. (Opcional) `fetch` de 2–3 páginas para más contexto.
4. **LLM (Claude)** redacta una respuesta **original** en español que integra lo
   publicado por Análisis + las fuentes web, **citando** (sin copiar texto).
5. Devolver `{answer, sources, related}`.

**Front:** definir `window.ANALISIS_ASK_URL = "<endpoint>"`. El hook ya existe en
el JS del asistente (`ASK_JS` en `build.py`); hay que actualizarlo para renderizar
las tres partes y para funcionar tanto en la barra de portada como en
`/asistente.html`.

## Recuperación de artículos relacionados
Reutilizar `search-index.json`. Para mejor precisión, generar **embeddings** del
archivo (una vez por build) y hacer similitud semántica con la pregunta. Devolver
3–5 artículos con título, sección, fecha y URL, clicables.

## Seguridad, costo y abuso (crítico — es un endpoint público con IA + búsqueda)
- **Rate limiting** por IP y **caché** de respuestas por pregunta normalizada.
- **Tope de gasto** (límite diario), **timeout** y **longitud máxima** de la
  pregunta.
- **Moderación** de la entrada (rechazar usos indebidos) y **CORS** restringido a
  `analisis.com`.
- Opcional: Cloudflare **Turnstile**/altcha para frenar bots.

## Legal / editorial
- **Citar** las fuentes externas con enlace; **no reproducir** su texto (síntesis
  propia; si se cita textual, <15 palabras entrecomilladas y atribuidas).
- Indicar que es una **respuesta generada por IA** y ofrecer los enlaces para
  verificar.

## Degradación (sin backend/clave)
Si `window.ANALISIS_ASK_URL` no está definido, mantener el **modo actual solo
interno** (extractivo sobre `search-index.json`): la barra sigue funcionando y
muestra artículos relacionados del sitio, sin búsqueda web ni redacción IA.

## Archivos
- **Nuevo backend:** `api/ask` (Worker/Función) — no vive en el repo estático o sí,
  según el host elegido.
- `generator/build.py`: insertar la barra en `_home` (sobre "5 claves"), y
  actualizar `ASK_JS` y `/asistente.html` para las tres partes de la respuesta.
- (Opcional) script de **embeddings** del archivo en el build.

## Criterios de aceptación
- En la portada, **sobre "Las 5 claves de hoy"**, hay una barra donde el usuario
  pregunta cualquier cosa.
- La respuesta se **elabora con información interna + web**, **cita fuentes
  externas** con enlace y **lista artículos de Análisis relacionados** clicables.
- Hay **rate limiting + caché + tope de gasto**; CORS restringido.
- Sin backend, la barra **degrada** al modo interno sin romperse.

## Decisiones a confirmar con Felipe (antes de implementar)
1. **Proveedor de búsqueda web:** Brave Search API (recomendado por precio/calidad
   y permiso de uso), Tavily (pensado para IA), o Bing/SerpAPI.
2. **Host del backend:** Cloudflare Workers (recomendado: barato, rápido, CORS
   sencillo) / Vercel / Netlify.
3. **¿Abierto a todos o solo a usuarios logueados?** (control de costo/abuso).
4. **Presupuesto mensual** tope para búsqueda + LLM.

---

### Prompt para pegar en Claude Code
```
Vamos a implementar T15 (ver TAREA-ASISTENTE.md): convertir "Pregúntale a Análisis"
en una barra principal en la portada, ARRIBA de "Las 5 claves de hoy", que responda
cualquier pregunta elaborando la respuesta con información interna (search-index)
y externa (búsqueda web) vía un backend serverless, citando fuentes y listando los
artículos de Análisis relacionados (clicables). Respeta la arquitectura, seguridad
(rate limit, caché, tope de gasto, CORS) y la degradación sin backend descritas en
el documento. Primero muéstrame: (a) tu propuesta de host del backend y proveedor
de búsqueda con costos estimados, y (b) el plan de cambios en build.py (ASK_JS,
_home, asistente.html) y el endpoint /ask, antes de programar.
```
