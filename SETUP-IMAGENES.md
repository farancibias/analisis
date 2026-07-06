# Portadas fotorrealistas con OpenAI GPT Image — configuración

El portal ya está integrado con **OpenAI GPT Image** para generar portadas
fotorrealistas. Se activa solo cuando defines la clave; si no, usa las portadas
ilustradas SVG (sin costo). Sigue estos pasos.

## 1. Consigue tu clave de API

1. Entra a la plataforma de OpenAI y crea una **API key** (empieza por `sk-...`).
2. Carga saldo o un método de pago (el uso de imágenes se factura por consumo).

## 2. Conecta la clave

**En GitHub (para la automatización 24 h):**
Repositorio → **Settings → Secrets and variables → Actions → New repository secret**
- Nombre: `OPENAI_API_KEY`
- Valor: tu clave `sk-...`

El workflow `.github/workflows/actualizar.yml` ya la usa y ejecuta
`pip install openai` automáticamente.

**Para probar en tu computador:**
```bash
export OPENAI_API_KEY="sk-..."
pip install openai
python3 generator/build.py      # las notas nuevas saldrán con foto de IA
```

## 3. Ajustes (opcionales)

Variables de entorno (ya puestas en el workflow con valores recomendados):

| Variable | Valor por defecto | Opciones |
|----------|-------------------|----------|
| `IMAGE_QUALITY` | `medium` | `low`, `medium`, `high` |
| `IMAGE_SIZE` | `1536x1024` | `1024x1024`, `1024x1536`, `1536x1024` |
| `IMAGE_MODEL` | `gpt-image-1.5` | otros modelos GPT Image |

El estilo base ("fotografía editorial, sin texto, sin logos…") está en
`generator/images.py` (variable `ESTILO`) — ajústalo a tu línea visual.
El *prompt* de cada nota viene del campo `image_prompt` en `content/articles.json`;
en las notas automáticas lo genera el pipeline.

## 4. Costo estimado

Con `medium` a 1536x1024, cada portada cuesta del orden de **US$0.03–0.06**
(verifica el precio vigente en la página de precios de OpenAI). A ~10 notas
nuevas por día:

- ~**US$0.30–0.60 al día** ≈ **US$9–18 al mes**.

Con `low` bajas el costo a la mitad; con `high` sube. El nivel `medium` es
suficiente para portadas web.

## 5. Caché: no pagas dos veces por la misma portada

Cada imagen generada se guarda en `content/covers/` (carpeta **versionada en Git**).
En cada build, si la portada de una nota ya existe, **se reutiliza sin volver a
llamar a la API**. Solo se genera imagen para las **notas nuevas** del día. Por eso
el workflow hace commit de `content/covers/` junto con `content/articles.json`.

**Regenerar una portada concreta:** borra su archivo en `content/covers/`
(`article-<id>.png`) y vuelve a construir; se generará de nuevo.

## 6. Respaldo automático

Si falta la clave, se agota el saldo o la API falla, `build.py` **no se rompe**:
cae de vuelta en la portada ilustrada SVG de esa nota y sigue publicando. En la
consola verás un aviso `falló la imagen IA (...); uso portada SVG`.

## 7. Nota legal (uso comercial)

OpenAI te asigna los derechos de uso del resultado, incluido el **uso comercial**,
así que no pagas licencias de banco de fotos. Ten en cuenta que una imagen 100%
generada por IA por lo general **no es registrable como copyright propio** (no
podrías impedir que un tercero la reutilice), pero sí puedes publicarla en el
portal sin problema. Revisa los términos vigentes de OpenAI al lanzar.

---

**Nota sobre las 4 portadas de muestra actuales:** son renders de las
ilustraciones generativas (crédito neutro "Portada · Análisis.com"). Cuando
publiques notas nuevas con la clave activa, esas saldrán como fotografías de IA.
Si quieres que las 4 de muestra también sean fotos de IA, borra sus archivos en
`content/covers/` y reconstruye con la clave puesta.
