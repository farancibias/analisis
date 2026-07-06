# Revisión del sitio en vivo (analisis.com) — mejoras sugeridas

Revisión hecha sobre la portada real del 6 de julio de 2026 (portada, ticker,
clima, tablero de datos y el listado completo de notas). El sitio funciona bien
técnicamente; las mayores oportunidades están hoy en **calidad editorial** y en
**foco regional**, más varias funciones que suman valor.

---

## A. Correcciones de calidad (prioridad alta — afectan credibilidad hoy)

1. **Relevancia de las imágenes.** La nota líder de hoy ("Los compradores del
   token $TRUMP acumulan pérdidas…") aparece ilustrada con una **foto de una
   protesta con carteles de Black Lives Matter y una pancarta con insulto a
   Trump**. La imagen no corresponde a la noticia y, además, es editorialmente
   riesgosa en un medio serio. El emparejamiento por palabra clave de Pexels es
   demasiado laxo. Recomendación:
   - Construir la búsqueda de imagen desde las **entidades/temas** de la nota, no
     desde el titular completo.
   - Umbral de pertinencia: si no hay buena foto, **caer a la portada ilustrada**
     (ya existe) en vez de forzar una foto dudosa.
   - Lista negra de resultados sensibles (protestas, banderas, personas
     identificables) salvo que la nota lo pida.
   - Etiquetar el crédito real (foto Pexels vs. ilustración vs. IA).

2. **Foco regional (América Latina).** La portada está **dominada por contenido
   británico/europeo**: "cartas al director de The Guardian sobre tuberculosis
   bovina", "una granja en Cumbria", "Sky compra ITV", "Starling Bank recorta
   130 empleos", "Novo Nordisk lanza Wegovy en Reino Unido", "regulador británico
   de pagos". Eso viene de que las fuentes RSS son mayoritariamente Guardian/BBC.
   Para un portal con foco LatAm:
   - **Sumar fuentes en español/regionales**: Bloomberg Línea, América Economía,
     Infobae, La Tercera/Emol/BioBioChile (CL), El Financiero/Expansión (MX),
     Valor Econômico/Folha (BR), El Comercio (PE), La Nación/Ámbito (AR),
     El Tiempo (CO), agencias EFE/Reuters LatAm.
   - **Puntaje de relevancia regional** para ordenar la portada: priorizar notas
     que mencionan países/empresas/mercados de la región.
   - **Filtrar no-noticias**: "cartas al director", opinión, live-blogs, obituarios
     locales irrelevantes.

3. **Selección de la nota líder.** Hoy la líder es una nota de cripto de 1 minuto.
   La portada debería elegir la líder por **importancia** (sección prioritaria +
   nº de fuentes + relevancia regional), no por ser la primera del día.

4. **Profundidad.** Muchas notas son de **"1 min de lectura"**. La ventaja
   competitiva es el contexto: combinar los clusters de fuentes en piezas más
   completas, con antecedentes y datos, y un "por qué importa".

5. **Deduplicación temática.** Hay pares casi iguales ("Cobre, litio y níquel
   impulsan un nuevo ciclo…" junto a "Cobre sobre US$6…"; dos notas de litio).
   Agrupar y evitar repetir el mismo tema el mismo día.

6. **Señales de confianza visibles.** Fecha y hora de actualización, nº de fuentes
   contrastadas y política de correcciones en cada nota (clave por ser contenido
   automatizado).

---

## B. Funcionalidades nuevas de alto valor

7. **Portada personalizada por país del usuario.** Ya detectas la ubicación por IP
   para el clima (hoy: Santiago). Usa esa señal para **priorizar noticias del país
   del lector** y ofrecer un selector de país. Gran diferenciador regional.

8. **"Mi Análisis" (ya hay Login).** Aprovechar el login para: seguir temas y
   secciones, guardar/leer después, y un **boletín personalizado**. Cierra el
   círculo de la personalización "Para ti".

9. **Resumen del día en portada.** Un briefing generado automáticamente ("Las 5
   claves de hoy") arriba de la portada. Es lo que más consume la audiencia.

10. **Audio briefing diario + voz de calidad.** Ya existe "Escuchar" (voz del
    navegador). Subir a una voz IA natural y publicar un **podcast diario** de
    3–5 min con el resumen. El 71% de los medios invierte más en audio.

11. **Alertas por tema/activo.** "Avísame cuando pase algo con el cobre / Codelco /
    el dólar" vía email, WhatsApp o Telegram (hooks ya implementados; falta
    activarlos con cuenta).

12. **Widgets de datos interactivos.** Sobre el tablero actual: **conversor de
    divisas**, calculadora de commodities y mini-gráficos embebidos dentro de las
    notas relacionadas (ej.: gráfico del cobre dentro de una nota de minería).

13. **Páginas por país y por empresa/entidad.** Ya generas páginas de tema; extender
    a **hubs de país** (Chile, Brasil, México…) y de **empresa** (Codelco, Vale,
    Petrobras) con su línea de tiempo. Suma páginas indexables y navegación.

14. **Traducción PT/EN en producción.** Portugués abre Brasil (el mayor mercado
    regional). El hook ya existe; falta activarlo.

15. **Optimización para respuestas de IA (AEO).** Como la gente consume noticias vía
    chatbots, estructurar cada nota con datos claros, FAQ y schema para **aparecer
    citado** en esas respuestas y recuperar tráfico.

---

## C. Formatos de contenido que atraen y retienen

16. **Explicadores y "en profundidad".** Piezas de contexto ("¿Por qué el cobre
    sobre US$6 tensiona a las fundiciones?") y un **glosario económico** enlazado
    desde las notas (TC/RC, riesgo país, carry trade…).

17. **Rankings y listas.** "Los unicornios de LatAm", "Mayores proyectos de litio",
    "Bancos por activos". Formato muy compartible y fácil de automatizar con datos.

18. **Newsletters temáticas por sección** (solo Minería, solo Economía…), además del
    boletín general.

19. **Tarjetas para redes sociales.** Generar automáticamente una imagen-resumen por
    nota (titular + dato clave) para Instagram/X/LinkedIn y ampliar alcance.

20. **Encuestas y reacciones** al pie de la nota para sumar interacción (y señal de
    interés para ordenar la portada).

---

## D. Producto y monetización (cuando haya audiencia)

21. **Suscripción/membresía** (sin anuncios, boletines premium, alertas, acceso al
    asistente y a informes).
22. **API de datos y reportes B2B** para empresas, mineras, bancos y consultoras
    (tu vertical de negocios lo hace especialmente vendible).
23. **Publicidad contextual** no invasiva por sección.

---

## Prioridad recomendada (primeros pasos)

| Orden | Acción | Por qué |
|-------|--------|---------|
| 1 | Arreglar relevancia de imágenes + lista negra + fallback ilustración | Riesgo de credibilidad **hoy** |
| 2 | Fuentes regionales + puntaje de relevancia + filtro de no-noticias | El portal debe sentirse latinoamericano |
| 3 | Selección de líder por importancia + deduplicación | Portada más seria y limpia |
| 4 | Portada priorizada por país del lector (reutiliza el geo del clima) | Diferenciador regional, bajo esfuerzo |
| 5 | Resumen del día + audio briefing + activar boletín/WhatsApp | Hábito y relación directa |

Los puntos 1–3 son de **calidad editorial** y conviene resolverlos antes de
empujar tráfico. Del 4 en adelante son funciones que amplían el valor.
