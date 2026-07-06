# Despliegue de Análisis.com (GitHub Pages)

El proyecto ya está **listo para publicar**: el generador emite el archivo `CNAME`
(analisis.com) y `.nojekyll`, y el workflow despliega en GitHub Pages en cada push.
Sigue estos pasos (los puede ejecutar Claude Code por ti).

> Estado del repo: ya está inicializado en la rama `main`, pero **falta el primer
> commit** (no se pudo crear en el entorno donde se preparó). Empieza por el Paso 1.

## Requisitos
- Git instalado. Opcional pero recomendado: GitHub CLI (`gh`).
- Una cuenta de GitHub.

## Paso 1 — Primer commit (en tu máquina)
```bash
cd "ruta/al/proyecto/analisis-com"
git add -A
git commit -m "Estado inicial de Análisis.com"
```
Si Git se queja del repo existente, parte de cero:
```bash
rm -rf .git && git init -b main && git add -A && git commit -m "Estado inicial de Análisis.com"
```

## Paso 2 — Crear el repositorio en GitHub y subir

**Opción A — con GitHub CLI (más rápido):**
```bash
gh repo create analisis --public --source=. --remote=origin --push
```

**Opción B — manual:**
1. Crea un repo vacío llamado `analisis` en github.com (sin README ni licencia).
2. ```bash
   git remote add origin https://github.com/TU-USUARIO/analisis.git
   git branch -M main
   git push -u origin main
   ```

El push dispara el workflow automáticamente (pestaña **Actions**).

## Paso 3 — Activar GitHub Pages
En el repo: **Settings → Pages → Build and deployment → Source: GitHub Actions.**
El workflow `actualizar.yml` ya hace el deploy. Espera a que termine el job
**publicar** en Actions (~1–2 min).

## Paso 4 — (Opcional) Conectar claves
**Settings → Secrets and variables → Actions → Secrets** (todos opcionales; el
sitio publica sin ellos):
- `PEXELS_API_KEY` — fotos reales de portada con licencia libre (gratis en pexels.com/api).
- `OPENAI_API_KEY` — portadas fotorrealistas por IA y traducción.
- `ANTHROPIC_API_KEY` — redacción automática de artículos. **Sin esta clave el
  pipeline NO genera notas nuevas** (se publica el contenido curado actual).
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — canal de Telegram.
- `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` — WhatsApp Cloud API.
- `EMAIL_API_KEY` — envío del boletín.

Pestaña **Variables**: `ANALYTICS_DOMAIN` (Plausible), `ADS` (`1` para anuncios).

## Paso 5 — Dominio analisis.com
1. **Settings → Pages → Custom domain:** escribe `analisis.com` y guarda.
   (El sitio ya incluye el archivo `CNAME`, así que se autocompleta.)
2. En tu **registrador DNS** crea:
   - **A** `@` →
     `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - **AAAA** `@` →
     `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153`
   - **CNAME** `www` → `TU-USUARIO.github.io`
3. Espera la propagación (minutos a horas). Luego marca **Enforce HTTPS** en Pages.

> El sitio está pensado para servirse en la **raíz** de un dominio (analisis.com).
> Mientras el DNS propaga puedes verlo en `https://TU-USUARIO.github.io/analisis/`,
> aunque algunas rutas absolutas (service worker, `data.json`) funcionan mejor ya
> con el dominio propio en la raíz.

## Paso 6 — Verificar
Abre el sitio y comprueba: ticker de datos bajo el menú, cuadro del clima en la
portada, buscador, asistente, `/datos.html`, y que las notas cargan con su portada.

## Operación diaria
El workflow corre solo cada día a las 09:00 UTC (06:00 CL/AR): actualiza datos,
genera el sitio, (si conectaste claves) redacta notas, distribuye titulares y
vuelve a publicar. También puedes lanzarlo a mano en **Actions → Run workflow**.

## Problemas frecuentes
- **El deploy falla:** confirma **Source = GitHub Actions** en Settings → Pages.
- **404 tras el push:** el primer deploy puede tardar; revisa la pestaña Actions.
- **Rutas rotas bajo `/analisis/`:** es por servir en subcarpeta; se resuelve al
  activar el dominio propio en la raíz (Paso 5).
- **No aparecen notas nuevas:** falta `ANTHROPIC_API_KEY` (es intencional hasta
  que conectes el modelo de redacción).
