# Análisis.com — Plan y arquitectura

Portal de noticias automatizado. Redacta artículos **originales** en español a partir
del contraste de múltiples fuentes internacionales fiables, se actualiza cada 24 h y
guarda todo el histórico para consulta.

---

## 1. Secciones del portal

Definidas contigo:

| # | Sección | Cobertura |
|---|---------|-----------|
| 1 | Tecnología | IA, software, semiconductores, innovación |
| 2 | Economía | Macro, bancos centrales, comercio, política fiscal |
| 3 | Minería | Cobre, litio, oro, minerales críticos |
| 4 | Agricultura | Commodities agrícolas, alimentos |
| 5 | Retail | Consumo, comercio minorista, e-commerce |
| 6 | Banca | Bancos, fintech, crédito, regulación |
| 7 | Energía y Medioambiente | Petróleo, gas, renovables, clima |
| 8 | Mercados y Cripto | Bolsas, divisas, materias primas, activos digitales |
| 9 | Internacional | Geopolítica, comercio, política internacional |
| 10 | Startups | Venture capital, emprendimiento, innovación |

Otras que puedes sumar más adelante según tráfico: **Salud/Farma**, **Inmobiliario**,
**Automotriz/Movilidad**, **Ciencia**, **Trabajo/Empleo**, **Pymes**.

---

## 2. Stack recomendado (y por qué)

**Sitio estático generado + GitHub Actions + GitHub Pages (o Netlify/Cloudflare Pages).**

- **Barato**: hosting estático es gratis o casi. Sin servidor que mantener.
- **Rápido y seguro**: HTML plano, sin base de datos que hackear, carga instantánea.
- **Encaja con la actualización cada 24 h**: una tarea programada (cron) regenera el
  sitio una vez al día. No necesitas un servidor encendido las 24 h.
- **Historial gratis**: cada actualización queda versionada en Git; el `articles.json`
  es el archivo maestro de todas las publicaciones.

Descartamos WordPress para el arranque porque añade costo, mantenimiento, plugins y
superficie de ataque que no necesitas sin equipo. Si en el futuro contratas editores
que quieran una interfaz visual, se puede migrar el contenido a un CMS headless
(Strapi, Sanity) manteniendo el mismo front estático.

**Componentes ya construidos en esta carpeta:**

```
analisis-com/
├── content/
│   └── articles.json          # ARCHIVO MAESTRO: todas las publicaciones (histórico)
├── generator/
│   ├── build.py               # genera el sitio estático completo desde articles.json
│   ├── pipeline.py            # recolecta, agrupa, redacta y guarda (corre cada 24h)
│   └── sources.json           # fuentes fiables por región y sección (RSS)
├── site/                      # SITIO GENERADO (esto es lo que se publica)
├── .github/workflows/
│   └── actualizar.yml         # automatización diaria (GitHub Actions)
└── PLAN.md
```

---

## 3. Flujo editorial automatizado (el corazón del proyecto)

Cada 24 h, `pipeline.py` ejecuta 5 etapas:

1. **Recolectar** — descarga titulares y resúmenes de las fuentes de `sources.json`
   (América, Europa, Asia) vía RSS.
2. **Agrupar** — detecta cuándo *la misma* noticia aparece en 2 o más medios distintos,
   comparando similitud de titulares. Sólo pasa el filtro lo cubierto por ≥2 fuentes:
   así se prioriza lo relevante y verificado, no el rumor de un solo medio.
3. **Redactar** — con el contexto de *todas* las fuentes del grupo, un modelo de IA
   escribe un artículo **nuevo desde cero**: sintetiza los hechos confirmados, aporta
   contexto y no reproduce frases de nadie. *(Este es el punto donde se conecta tu clave
   de API — ver sección 5.)*
4. **Guardar** — el artículo se añade a `articles.json` con fecha e ID único. Nunca se
   borra nada: ese archivo ES el histórico consultable.
5. **Publicar** — `build.py` regenera el sitio (portada, secciones, artículos, archivo).

---

## 4. Fuentes fiables por región

Configuradas en `generator/sources.json`. Selección de arranque:

- **América**: AP, CNBC, Reuters, Reporte Minero (Chile), Retail Dive, TechCrunch.
- **Europa**: BBC, The Guardian, El País, Finextra.
- **Asia**: Nikkei Asia (y se pueden sumar The Japan Times, South China Morning Post,
  The Straits Times).
- **Globales/sectoriales**: Reuters, Mining.com, OilPrice, CoinDesk.

Puedes editar esa lista libremente: cada entrada define nombre, región, sección y URL
del feed. Cuantas más fuentes fiables por sección, mejor el contraste y la detección de
la "misma noticia".

---

## 5. Cómo activar la redacción con IA

En `pipeline.py`, la función `redactar()` tiene el punto exacto de conexión. Pasos:

1. Consigue una clave de API de un proveedor de modelos de lenguaje.
2. En GitHub: **Settings → Secrets and variables → Actions → New secret**,
   nombre `ANTHROPIC_API_KEY` (ya referenciado en el workflow).
3. Descomenta el bloque de ejemplo de `redactar()` y ajusta el modelo.

El *prompt* de redacción ya está escrito (`REDACCION_PROMPT`) y exige: usar sólo hechos
presentes en las fuentes, no copiar frases, atribuir datos exclusivos y tono informativo.

---

## 6. Consideraciones legales y de calidad (importante)

- **Los hechos no tienen copyright.** Reportar que "el cobre superó los US$6" es libre.
  Lo protegido es la *expresión* concreta de cada medio: sus frases, su estructura, sus
  fotos. Por eso el pipeline **redacta de cero**, no parafrasea.
- **Verifica con ≥2 fuentes** antes de publicar (ya es una regla del pipeline).
- **Atribuye lo exclusivo**: si un dato o declaración viene de un solo medio, cítalo
  ("según Reuters…").
- **No republiques fotos** de las fuentes sin licencia. Usa bancos con licencia libre
  (Unsplash, Pexels), imágenes propias o ilustraciones generadas.
- **Respeta los términos de cada feed**: los RSS son para consumo de titulares/resúmenes.
- **Transparencia**: cada artículo del prototipo incluye una nota que aclara que es
  redacción propia a partir del contraste de fuentes. Recomiendo mantenerla.
- Copiar y sólo "cambiar palabras" sí genera riesgo legal y de reputación. El diseño
  evita eso por construcción.

---

## 7. Hoja de ruta sugerida

**Fase 1 — Puesta en marcha (esta semana)**
- Revisar el prototipo (ya generado en `site/`).
- Crear repo en GitHub, subir esta carpeta, activar GitHub Pages.
- Apuntar el dominio `analisis.com` al hosting (DNS).

**Fase 2 — Automatización real (semana 1–2)**
- Conseguir clave de API y activar `redactar()`.
- Afinar `sources.json` (más fuentes asiáticas, medios en español).
- Primera corrida automática supervisada; ajustar umbrales de agrupación.

**Fase 3 — Calidad y crecimiento (mes 1–2)**
- Imágenes (banco con licencia o generación).
- SEO: metadatos, sitemap.xml, datos estructturados, Open Graph.
- Newsletter diaria automática con los titulares del día.
- Analítica (Plausible/GA) para ver qué secciones rinden.

**Fase 4 — Escala (mes 3+)**
- Revisión humana editorial (aunque sea ligera) antes de publicar temas sensibles.
- Más secciones según tráfico.
- Eventual CMS headless si sumas editores.

---

## 8. Cómo probar el prototipo ahora

Desde la carpeta `analisis-com/`:

```bash
python3 generator/build.py            # regenera el sitio
cd site && python3 -m http.server 8000
# abre http://localhost:8000 en el navegador
```

Para simular la actualización diaria (con la etapa de IA aún en modo borrador):

```bash
pip install feedparser
python3 generator/pipeline.py         # recolecta, agrupa y guarda
python3 generator/build.py            # publica
```
