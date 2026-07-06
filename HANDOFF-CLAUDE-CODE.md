# Prompt de traspaso para Claude Code

Copia y pega el bloque de abajo en Claude Code, abierto en la carpeta
`analisis-com/`. Ajusta lo que esté entre〈corchetes〉.

---

```
Estoy retomando un proyecto llamado "Análisis.com": un portal de noticias
regional (foco América Latina) totalmente AUTOMATIZADO, sin equipo de redacción.
Redacta artículos ORIGINALES en español contrastando múltiples fuentes
internacionales, genera portadas por IA, se actualiza cada 24 h, guarda todo el
histórico y se publica como sitio ESTÁTICO (estilo editorial tipo El País / WSJ).

CÓMO EMPEZAR
Antes de tocar nada, lee estos archivos en la raíz del repo, en este orden:
README.md, DESPLIEGUE.md, PLAN.md, FUNCIONES.md, ROADMAP-MEJORAS.md, SETUP-IMAGENES.md.
Luego revisa generator/build.py (núcleo del generador), generator/images.py,
generator/pipeline.py y content/articles.json (archivo maestro de contenido).

ARQUITECTURA (resumen)
- Sitio estático generado con Python. Sin backend ni base de datos.
- Contenido maestro: content/articles.json. Datos del tablero: content/data.json.
- Portadas cacheadas y versionadas en content/covers/ (para no re-pagar imágenes).
- Generador: `python3 generator/build.py` crea todo en site/.
- Automatización diaria: .github/workflows/actualizar.yml orquesta
  pipeline → fetch_data → translate(opcional) → build → distribute → deploy Pages.
- Regla de oro del código: TODA integración externa (OpenAI, datos, WhatsApp,
  etc.) debe degradar con gracia si falta la clave; el build nunca debe romperse.
- Probar en local:
    pip install -r requirements.txt
    python3 generator/build.py
    cd site && python3 -m http.server 8000

ESTADO ACTUAL (funciona ya, sin claves)
Portal con portadas; 4 artículos de muestra; claves en 30s; escuchar nota
(Web Speech); modo oscuro; tamaño de fuente; tiempo de lectura; compartir;
relacionadas; búsqueda; asistente "Pregúntale a Análisis" (extractivo);
páginas de tema con línea de tiempo; ticker de datos en movimiento bajo el menú
(monedas en vivo vía open.er-api.com); cuadro del clima por geolocalización
(Open-Meteo + ipwho.is) en portada; tablero /datos.html; boletín diario;
personalización "Para ti"; PWA offline/instalable; SEO (JSON-LD, sitemaps,
robots, RSS). Detalle en FUNCIONES.md.

IMPLEMENTADO CON HOOK (requiere que yo conecte una clave/cuenta)
Portadas fotorrealistas (OpenAI GPT Image, ver SETUP-IMAGENES.md), redacción con
IA en pipeline.py, datos en vivo de commodities en fetch_data.py, traducción
PT/EN en translate.py, Telegram/WhatsApp/email en distribute.py, asistente RAG
generativo (endpoint window.ANALISIS_ASK_URL), analítica y anuncios.

QUÉ NECESITO QUE HAGAS AHORA (TAREA PRINCIPAL: DESPLEGAR)
Publica el sitio en GitHub Pages siguiendo DESPLIEGUE.md al pie de la letra:
1) Haz el primer commit (el repo ya está inicializado en la rama main, pero SIN
   commit todavía).
2) Crea el repositorio en GitHub (usa `gh repo create analisis --public
   --source=. --remote=origin --push` si tengo GitHub CLI; si no, guíame el modo
   manual) y sube el código.
3) Activa GitHub Pages con Source = GitHub Actions y verifica que el workflow
   `actualizar.yml` despliega bien (pestaña Actions).
4) Dame los pasos exactos de DNS para apuntar analisis.com (ya hay archivo CNAME
   en el sitio) y de dónde cargar los secrets/variables.
Cuando esté publicado, confírmame la URL y que el ticker, el clima, el buscador,
el asistente y /datos.html funcionan.

DESPUÉS (siguientes tareas, cuando te lo pida)
- Backend mínimo del asistente RAG (embeddings del archivo + endpoint /ask que
  reciba {q} y devuelva {answer} citando artículos) conectado con
  window.ANALISIS_ASK_URL.
- Datos reales de commodities en generator/fetch_data.py (con fallback).
- Envío real del boletín por email y canal de Telegram en distribute.py.
- Traducción PT/EN en producción.

RESTRICCIONES Y CONVENCIONES
- Mantén el estilo editorial y la estructura del generador; no rehagas el diseño.
- No introduzcas dependencias pesadas ni un CMS; sigue siendo estático.
- Respeta el modelo de caché de portadas (content/covers/).
- Consideración legal ya asumida: los artículos son redacción propia (no copiar
  frases), verificar con ≥2 fuentes, atribuir datos exclusivos.
- Antes de dar por terminada una tarea: corre `python3 generator/build.py`,
  sírvelo en local y verifica que las páginas afectadas funcionan.

CONTEXTO DE NEGOCIO
La estrategia diferenciadora (ver ROADMAP-MEJORAS.md) es no competir con los
chatbots resumiendo, sino ser la capa de CONTEXTO + DATOS regionales + interacción
(asistente, tablero, WhatsApp, audio). Prioriza eso en las decisiones de producto.

Empieza confirmándome que leíste los documentos y proponme un plan corto antes de
implementar.
```
