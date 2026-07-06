#!/usr/bin/env python3
"""
Generador de sitio estático para Análisis.com (versión ampliada).
Estilo editorial (El País / WSJ) + suite de funciones:
  claves, escuchar nota (TTS), modo oscuro, tamaño de fuente, tiempo de lectura,
  relacionados, compartir, búsqueda, asistente 'Pregúntale a Análisis',
  páginas de tema con línea de tiempo, tablero de datos, boletín diario,
  SEO (JSON-LD, sitemaps, RSS), PWA (offline/instalable) y personalización.

Ejecutar:  python3 generator/build.py
"""

import hashlib
import json
import os
import re
import shutil
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from html import escape

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from images import cover_svg, build_cover, SECTION_VISUAL  # noqa: E402
from audio import build_audio, build_briefing  # noqa: E402
from pipeline import (puntaje_regional, paises_de, empresas_de,  # noqa: E402
                      PAIS_NOMBRE, EMPRESAS)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content", "articles.json")
DATA = os.path.join(ROOT, "content", "data.json")
OUT = os.path.join(ROOT, "site")
IMGDIR = os.path.join(OUT, "img")
COVERS_DIR = os.path.join(ROOT, "content", "covers")
AUDIO_OUT = os.path.join(OUT, "audio")
AUDIO_DIR = os.path.join(ROOT, "content", "audio")

SITE_URL = os.environ.get("SITE_URL", "https://www.analisis.com").rstrip("/")
ANALYTICS_DOMAIN = os.environ.get("ANALYTICS_DOMAIN", "")  # p.ej. analisis.com (Plausible)
GA4_ID = os.environ.get("GA4_ID", "")                      # id de medición GA4 (G-XXXX) para el tracking
ASK_URL = os.environ.get("ASK_URL", "")                    # endpoint /api/ask (T15); sin él, asistente en modo interno
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD") or "analisis"  # clave del panel privado (/panel.html)
ANALYTICS_JSON = os.path.join(ROOT, "content", "analytics.json")
DIGEST_JSON = os.path.join(ROOT, "content", "digest.json")
ADS = os.environ.get("ADS", "") == "1"

COVER = {}
CREDIT = {}   # id de artículo -> crédito de la foto (atribución), si aplica
AUDIO = {}    # id de artículo -> nombre del MP3 de voz neuronal, si existe
BRIEFING = None  # nombre del MP3 del briefing del día, si existe
SERIES_BY_ID = {}  # id de serie (data.json) -> serie, para los mini-gráficos (T11)
ENGAGEMENT = {}    # id de artículo -> nº de interacciones (GA4), señal de interés
# Sección -> serie de datos a incrustar como mini-gráfico en sus artículos.
SECTION_SERIE = {"mineria": "cobre", "mercados": "oro", "agricultura": "trigo"}
TICKER_HTML = ""
ASSET_VER = ""  # hash del bundle (CSS+JS) para versionar app.css/app.js y bustear la caché de Cloudflare

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d.day} de {MESES[d.month]} de {d.year}"


def fecha_hora(a):
    """Fecha (y hora UTC si se guardó) de última actualización de la nota."""
    upd = a.get("updated")
    if upd and "T" in upd:
        dia, hora = upd.split("T")
        return f"{fecha_larga(dia)}, {hora[:5]} UTC"
    return fecha_larga(a["date"])


def slugify(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def reading_time(a):
    words = sum(len(p.split()) for p in a["body"])
    return max(1, round(words / 200))


# ============================================================ estilo + scripts
CSS = """
:root{
  --ink:#111417;--muted:#6b7178;--line:#e2e2e0;--line2:#c9c9c6;--red:#c00000;
  --brand-1:#241a9c;--brand-2:#3f2be6;--brand-3:#ec1414;
  --bg:#ffffff;--wash:#f6f5f2;--card:#ffffff;
  --serif:'Source Serif 4',Georgia,'Times New Roman',serif;
  --sans:'Libre Franklin',system-ui,-apple-system,Helvetica,Arial,sans-serif;}
html[data-tema=oscuro]{--ink:#e9eaec;--muted:#9aa1a9;--line:#2a2d31;--line2:#3a3d42;
  --bg:#0f1113;--wash:#17191c;--card:#141619;--red:#ff5a4d;
  --brand-1:#5b4fe6;--brand-2:#7c6bff;--brand-3:#ff5a4d;}
html{font-size:var(--fs,17px)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--serif);line-height:1.5}
a{color:inherit;text-decoration:none}
img{display:block;width:100%;height:100%;object-fit:cover}
.wrap{max-width:1120px;margin:0 auto;padding:0 22px}
.progress{position:fixed;top:0;left:0;height:3px;background:var(--red);width:0;z-index:99}
header.site{border-bottom:2px solid var(--ink);background:var(--bg)}
.strip{border-bottom:1px solid var(--line);font-family:var(--sans);font-size:12px;color:var(--muted);
  display:flex;justify-content:space-between;align-items:center;padding:6px 0;gap:10px}
.tools{display:flex;gap:6px;align-items:center}
.tools button,.tools a.tb{font-family:var(--sans);font-size:12px;color:var(--muted);background:none;
  border:1px solid var(--line);border-radius:4px;padding:3px 8px;cursor:pointer}
.tools button:hover,.tools a.tb:hover{color:var(--red);border-color:var(--red)}
.masthead{text-align:center;padding:15px 0 9px}
.brand{display:inline-flex;align-items:center;gap:13px}
.brand .mark{width:48px;height:48px;flex:none;display:block}
.brand .mark circle{transform-box:fill-box;transform-origin:center}
.brand .mark .r1{stroke:var(--brand-1);animation:girar 14s linear infinite}
.brand .mark .r2{stroke:var(--brand-2);animation:girar 9s linear infinite reverse}
.brand .mark .r3{stroke:var(--brand-3);animation:girar 6s linear infinite}
@keyframes girar{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.brand .mark .r1,.brand .mark .r2,.brand .mark .r3{animation:none}}
.brand:hover .mark .r1{animation-duration:7s}
.brand:hover .mark .r2{animation-duration:4.5s}
.brand:hover .mark .r3{animation-duration:3s}
.brand .wm{font-family:var(--sans);font-weight:800;font-size:40px;letter-spacing:-1px;line-height:1;color:var(--brand-3)}
.masthead .sub{font-family:var(--sans);font-size:12px;letter-spacing:.5px;color:var(--muted);text-transform:uppercase;margin-top:2px}
nav.main{border-top:1px solid var(--line);border-bottom:1px solid var(--ink)}
nav.main .wrap{display:flex;flex-wrap:wrap;justify-content:center}
nav.main a{font-family:var(--sans);font-size:12.5px;font-weight:600;text-transform:uppercase;letter-spacing:.4px;color:var(--ink);padding:10px 11px}
nav.main a:hover,nav.main a.active{color:var(--red)}
.kicker{font-family:var(--sans);font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--red)}
.meta{font-family:var(--sans);font-size:12px;color:var(--muted)}
.lead-grid{display:grid;grid-template-columns:1.55fr 1fr;gap:0;margin:24px 0 8px;border-bottom:1px solid var(--ink);padding-bottom:24px}
.lead-main{padding-right:30px;border-right:1px solid var(--line)}
.lead-main .thumb{aspect-ratio:16/9;overflow:hidden;background:var(--wash);margin-bottom:14px}
.lead-main h1{font-size:42px;line-height:1.08;font-weight:800;margin:.18em 0 .12em;letter-spacing:-.5px}
.lead-main h1 a:hover{color:var(--red)}
.lead-main .dek{font-size:19px;color:var(--muted);line-height:1.42;margin:.2em 0 .5em}
.whatsnews{padding-left:26px}
.whatsnews h4{font-family:var(--sans);font-size:12px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid var(--ink);padding-bottom:6px;margin:0 0 4px}
.wn-item{padding:12px 0;border-bottom:1px solid var(--line)}
.wn-item .t{font-size:17px;font-weight:700;line-height:1.22}
.wn-item .t a:hover{color:var(--red)}
.wn-list{max-height:380px;overflow-y:auto;overflow-x:hidden;padding-right:10px;scrollbar-width:thin;scrollbar-color:var(--line2) transparent}
.wn-list::-webkit-scrollbar{width:8px}
.wn-list::-webkit-scrollbar-thumb{background:var(--line2);border-radius:4px}
.wn-list::-webkit-scrollbar-track{background:var(--wash);border-radius:4px}
.wn-list .wn-item:first-child{padding-top:2px}
.wn-list .wn-item:last-child{border-bottom:0}
.section-head{display:flex;align-items:baseline;gap:12px;border-bottom:2px solid var(--ink);margin:28px 0 16px;padding-bottom:6px;flex-wrap:wrap}
.section-head h2{font-family:var(--sans);font-size:15px;text-transform:uppercase;letter-spacing:1px;margin:0}
.section-head .d{font-family:var(--sans);font-size:12px;color:var(--muted)}
.paispick{font-family:var(--sans);font-size:12px;color:var(--muted);margin-left:auto;display:flex;align-items:center;gap:6px}
.paispick select{font-family:var(--sans);font-size:12px;color:var(--ink);background:var(--wash);border:1px solid var(--line);border-radius:4px;padding:4px 6px;cursor:pointer}
.claves-dia{margin:16px 0 6px;padding:14px 18px 16px;background:var(--wash);border:1px solid var(--line);border-radius:6px}
.claves-dia .section-head{margin:0 0 8px;border-bottom-width:1px;align-items:center}
.cd-intro{font-family:var(--serif);font-size:15px;color:var(--ink);margin:0 0 10px}
.cd-list{margin:0;padding-left:22px}
.cd-list li{margin:5px 0;font-family:var(--sans);font-size:14px}
.cd-list a{color:var(--ink);text-decoration:none}
.cd-list a:hover{color:var(--red)}
.cd-list .kicker{margin-right:6px}
.cd-audio{margin-left:auto}
.cd-audio audio{width:260px;max-width:48vw;height:32px;vertical-align:middle}
.cd-listen{font-family:var(--sans);font-size:12.5px;color:var(--ink);background:var(--wash);border:1px solid var(--line);border-radius:4px;padding:6px 12px;cursor:pointer}
.cd-listen:hover{color:var(--red);border-color:var(--red)}
.tool .toolrow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:8px 0}
.tool input,.tool select{font-family:var(--sans);font-size:14px;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:6px 8px}
.tool input{width:96px}
.toolout{font-family:var(--sans);font-size:15px;font-weight:600;color:var(--ink);margin:4px 0 2px}
.art-chart{margin:22px 0;padding:12px 14px}
.art-chart canvas{max-height:220px}
.faq{margin:24px 0;border-top:1px solid var(--line);padding-top:14px}
.faq h4{font-family:var(--sans);font-size:13px;text-transform:uppercase;letter-spacing:.5px;margin:0 0 10px}
.faq details{border-bottom:1px solid var(--line);padding:9px 0}
.faq summary{font-family:var(--serif);font-size:16px;font-weight:600;cursor:pointer;color:var(--ink)}
.faq details p{font-family:var(--serif);font-size:15px;color:var(--ink);margin:8px 0 2px}
.react{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:22px 0 6px;font-family:var(--sans)}
.react-q{font-size:13px;color:var(--muted);margin-right:2px}
.react button,.poll-opts button{font-family:var(--sans);font-size:13px;color:var(--ink);background:var(--wash);border:1px solid var(--line);border-radius:20px;padding:6px 12px;cursor:pointer}
.react button:hover,.poll-opts button:hover{border-color:var(--red)}
.react button.on,.poll-opts button.on{background:var(--red);color:#fff;border-color:var(--red)}
.poll-opts button:disabled{cursor:default;opacity:.85}
.poll{margin:14px 0 6px;padding:14px 16px;background:var(--wash);border:1px solid var(--line);border-radius:6px}
.poll h4{font-family:var(--sans);font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin:0 0 6px}
.poll-q{font-family:var(--serif);font-size:16px;font-weight:600;margin:0 0 10px}
.poll-opts{display:flex;gap:8px;flex-wrap:wrap}
.poll-thanks{font-family:var(--sans);font-size:12.5px;color:var(--red);margin:10px 0 0}
.ask-hero{margin:14px 0 2px}
.ask-row{display:flex;gap:8px}
.ask-q{flex:1;font-family:var(--sans);font-size:16px;color:var(--ink);background:var(--bg);border:1px solid var(--ink);border-radius:6px;padding:12px 14px}
.ask-q:focus{outline:none;border-color:var(--red)}
.ask-go{font-family:var(--sans);font-size:14px;font-weight:600;color:#fff;background:var(--red);border:1px solid var(--red);border-radius:6px;padding:0 20px;cursor:pointer}
.ask-go:hover{opacity:.9}
.ask-chips{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 0}
.ask-chip{font-family:var(--sans);font-size:12.5px;color:var(--muted);background:var(--wash);border:1px solid var(--line);border-radius:20px;padding:5px 11px;cursor:pointer}
.ask-chip:hover{color:var(--red);border-color:var(--red)}
.ask-out:not(:empty){margin:14px 0 4px;padding:14px 16px;background:var(--wash);border:1px solid var(--line);border-radius:6px}
.ask-loading{font-family:var(--sans);font-size:13px;color:var(--muted);margin:0}
.ask-ans p{font-family:var(--serif);font-size:16px;line-height:1.55;margin:0 0 10px}
.ask-ans ul{margin:0 0 10px;padding-left:20px}
.ask-ans li{font-family:var(--serif);font-size:15px;line-height:1.5;margin:4px 0}
.ask-src,.ask-rel{margin:12px 0 0;border-top:1px solid var(--line);padding-top:10px}
.ask-src h4,.ask-rel h4{font-family:var(--sans);font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin:0 0 7px}
.ask-src a{display:block;font-family:var(--sans);font-size:13px;color:var(--ink);text-decoration:none;margin:5px 0}
.ask-src a:hover{color:var(--red)}
.ask-dom{color:var(--red);font-weight:600}
.ask-card{display:block;font-family:var(--sans);font-size:14px;color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line);padding:7px 0}
.ask-card:last-child{border-bottom:0}
.ask-card:hover{color:var(--red)}
.ask-card .kicker{display:block;margin-bottom:2px}
.ask-note{margin:12px 0 0}
.langwrap{position:relative;display:inline-block}
.langmenu{position:absolute;right:0;top:100%;margin-top:4px;background:var(--bg);border:1px solid var(--ink);border-radius:6px;box-shadow:0 6px 20px rgba(0,0,0,.15);z-index:50;min-width:130px;overflow:hidden}
.langmenu[hidden]{display:none}
.langmenu a{display:block;font-family:var(--sans);font-size:13px;color:var(--ink);text-decoration:none;padding:8px 14px}
.langmenu a:hover{background:var(--wash);color:var(--red)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:26px}
@media(max-width:820px){.lead-grid{grid-template-columns:1fr}.lead-main{border-right:0;padding-right:0}.whatsnews{padding-left:0;margin-top:20px}.grid{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.grid{grid-template-columns:1fr}.brand .wm{font-size:30px}.brand .mark{width:40px;height:40px}}
.card{background:var(--card)}
.card .thumb{aspect-ratio:16/9;overflow:hidden;background:var(--wash);margin-bottom:11px}
.card h3{font-size:21px;line-height:1.18;font-weight:700;margin:.25em 0 .2em}
.card:hover h3{color:var(--red)}
.card .dek{font-size:15.5px;color:var(--muted);line-height:1.4;margin:.1em 0 .4em}
.card.placeholder{opacity:.7}
.card.placeholder .badge{font-family:var(--sans);font-size:11px;color:var(--muted)}
article.post{max-width:720px;margin:24px auto 0}
article.post h1{font-size:40px;line-height:1.1;font-weight:800;letter-spacing:-.5px;margin:.15em 0 .2em}
article.post .dek{font-size:21px;color:var(--muted);line-height:1.4;margin:.1em 0 .6em}
.byline{font-family:var(--sans);font-size:13px;color:var(--muted);border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:11px 0;margin:14px 0 18px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center}
.byline .acts{display:flex;gap:6px}
.byline button{font-family:var(--sans);font-size:12px;color:var(--ink);background:var(--wash);border:1px solid var(--line);border-radius:4px;padding:5px 10px;cursor:pointer}
.byline button:hover{color:var(--red);border-color:var(--red)}
.trust{font-family:var(--sans);font-size:12px;color:var(--muted);margin:-6px 0 18px}
.trust a{color:var(--muted);text-decoration:underline}
.trust a:hover{color:var(--red)}
figure.hero{margin:0 0 20px}
figure.hero .thumb{aspect-ratio:16/9;overflow:hidden;background:var(--wash)}
figure.hero figcaption{font-family:var(--sans);font-size:12px;color:var(--muted);padding-top:7px;border-bottom:1px solid var(--line);padding-bottom:12px}
.claves{background:var(--wash);border:1px solid var(--line);border-left:4px solid var(--red);border-radius:6px;padding:14px 18px;margin:0 0 22px}
.claves h4{font-family:var(--sans);font-size:12px;text-transform:uppercase;letter-spacing:.8px;margin:0 0 8px}
.claves ul{margin:0;padding-left:18px}
.claves li{font-size:16px;margin:5px 0;line-height:1.4}
article.post p{font-size:18.5px;line-height:1.62;margin:1.05em 0}
.tag{display:inline-block;font-family:var(--sans);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.4px;color:var(--ink);border:1px solid var(--line2);padding:4px 10px;border-radius:2px;margin:4px 5px 0 0}
.tag:hover{border-color:var(--red);color:var(--red)}
.note{background:var(--wash);border-left:3px solid var(--red);padding:12px 16px;font-family:var(--sans);font-size:12.5px;color:var(--muted);margin-top:24px;line-height:1.5}
.related{margin:30px 0}
.arch-day{font-family:var(--sans);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;border-bottom:2px solid var(--ink);padding-bottom:6px;margin:28px 0 16px}
footer.site{border-top:2px solid var(--ink);margin-top:48px;padding:26px 0;font-family:var(--sans);font-size:12.5px;color:var(--muted)}
footer.site a{color:var(--muted);text-decoration:underline}
footer.site strong{color:var(--ink)}
.brand-foot{gap:10px;margin-bottom:4px}
.brand-foot .mark{width:30px;height:30px}
.brand-foot .wm{font-size:23px}
footer.site .foot-tag{margin-bottom:10px}
.searchbox{width:100%;font-family:var(--sans);font-size:18px;padding:14px 16px;border:2px solid var(--ink);border-radius:6px;background:var(--card);color:var(--ink)}
.ans{background:var(--wash);border:1px solid var(--line);border-radius:8px;padding:18px 20px;margin:16px 0;font-size:18px;line-height:1.5}
.ad{background:var(--wash);border:1px dashed var(--line2);border-radius:6px;text-align:center;color:var(--muted);
  font-family:var(--sans);font-size:12px;padding:18px;margin:22px 0}
.chip{display:inline-block;font-family:var(--sans);font-size:12px;font-weight:600;border:1px solid var(--line2);border-radius:20px;padding:5px 12px;margin:3px 4px 0 0;cursor:pointer;color:var(--ink)}
.chip.on{background:var(--red);color:#fff;border-color:var(--red)}
.tl{border-left:2px solid var(--line);margin-left:8px;padding-left:18px}
.tl .it{position:relative;padding:12px 0;border-bottom:1px solid var(--line)}
.tl .it::before{content:"";position:absolute;left:-25px;top:18px;width:10px;height:10px;background:var(--red);border-radius:50%}
.dgrid{display:grid;grid-template-columns:1fr 1fr;gap:22px}
@media(max-width:700px){.dgrid{grid-template-columns:1fr}}
.dcard{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px}
table.rates{width:100%;border-collapse:collapse;font-family:var(--sans);font-size:14px}
table.rates th,table.rates td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line)}
/* ticker de mercados */
.ticker{display:flex;align-items:stretch;background:#111417;color:#fff;border-bottom:2px solid var(--red);font-family:var(--sans);font-size:13px;overflow:hidden}
.ticker-lbl{display:flex;align-items:center;background:var(--red);color:#fff;font-weight:700;font-size:11px;letter-spacing:1px;padding:0 12px;white-space:nowrap;z-index:2}
.ticker-vp{overflow:hidden;flex:1}
.ticker-track{display:inline-flex;gap:34px;padding:7px 0;white-space:nowrap;animation:tkmove 60s linear infinite}
.ticker:hover .ticker-track{animation-play-state:paused}
@keyframes tkmove{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.tk{display:inline-flex;gap:7px;align-items:baseline;color:#fff}
.tk b{font-weight:700}
.tk .up{color:#39d98a}.tk .down{color:#ff6b6b}.tk .flat{color:#aab}
/* cuadro de clima */
.wx{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:0 0 18px}
.wx-top{display:flex;align-items:center;gap:12px}
.wx-emoji{font-size:42px;line-height:1}
.wx-temp{font-size:32px;font-weight:800;line-height:1.1}
.wx-place{font-family:var(--sans);font-size:12.5px;color:var(--muted)}
.wx-cond{font-family:var(--sans);font-size:13px;color:var(--ink)}
.wx-fc{display:flex;gap:8px;margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
.wx-day{flex:1;text-align:center;font-family:var(--sans);font-size:12px;color:var(--muted)}
.wx-day .e{font-size:20px;margin:2px 0}
.wx-day .mm{color:var(--ink);font-weight:700}
"""

APP_JS = r"""
(function(){
  var d=document,ls=window.localStorage,H=d.documentElement;
  // tema
  var tema=ls.getItem('tema'); if(tema)H.setAttribute('data-tema',tema);
  window.toggleTema=function(){var n=H.getAttribute('data-tema')==='oscuro'?'':'oscuro';
    if(n)H.setAttribute('data-tema',n);else H.removeAttribute('data-tema');ls.setItem('tema',n);};
  // tamaño de texto: el CSS usa px, así que escalamos el bloque de contenido con zoom
  function _zoom(z){var m=d.querySelector('main'); if(m)m.style.zoom=z;}
  var _z=ls.getItem('zoom'); if(_z)_zoom(_z);
  window.fuente=function(step){var z=parseFloat(ls.getItem('zoom')||'1');
    z=Math.min(1.4,Math.max(0.85,Math.round((z+step*0.1)*100)/100));
    _zoom(z);ls.setItem('zoom',z);};
  // barra de progreso (en artículos)
  var bar=d.querySelector('.progress');
  if(bar)window.addEventListener('scroll',function(){var h=d.body.scrollHeight-innerHeight;
    bar.style.width=(h>0?(scrollY/h*100):0)+'%';});
  // escuchar nota: audio neural pregenerado si existe; si no, la MEJOR voz del navegador
  var _voz=null,_vocesListas=false;
  function _elegirVoz(){var sy=window.speechSynthesis;if(!sy)return null;
    var vs=sy.getVoices()||[];var es=vs.filter(function(v){return /^es(-|_|$)/i.test(v.lang);});
    if(!es.length)es=vs;
    var buenas=/(natural|neural|online|enhanced|premium|google|siri|m[oó]nica|paulina|elvira|dalia|lupe|lucia|sergio)/i;
    var malas=/(compact|eloquence|espeak|pico)/i;
    function sc(v){var s=0;if(buenas.test(v.name))s+=10;if(malas.test(v.name))s-=8;
      if(/es[-_]ES/i.test(v.lang))s+=2;if(/es[-_](MX|US|419|AR|CL)/i.test(v.lang))s+=1;
      if(!v.localService)s+=3;return s;}
    es.sort(function(a,b){return sc(b)-sc(a);});return es[0]||null;}
  function _cargarVoces(cb){var sy=window.speechSynthesis;if(!sy){cb();return;}
    var v=sy.getVoices();if(v&&v.length){_voz=_elegirVoz();_vocesListas=true;cb();return;}
    sy.onvoiceschanged=function(){if(_vocesListas)return;_voz=_elegirVoz();_vocesListas=true;cb();};
    setTimeout(function(){if(_vocesListas)return;_voz=_elegirVoz();_vocesListas=true;cb();},500);}
  function _hablar(texto,btn){var sy=window.speechSynthesis;
    var partes=texto.replace(/\s+/g,' ').match(/[^.!?…]+[.!?…]*/g)||[texto];var i=0;
    function sig(){if(i>=partes.length){btn.textContent='▶ Escuchar';return;}
      var frag=partes[i].trim();if(!frag){i++;return sig();}
      var u=new SpeechSynthesisUtterance(frag);u.lang=(_voz&&_voz.lang)||'es-ES';
      if(_voz)u.voice=_voz;u.rate=1;u.pitch=1;
      u.onend=function(){i++;sig();};u.onerror=function(){btn.textContent='▶ Escuchar';};
      sy.speak(u);}
    sig();}
  window.leer=function(btn){
    var pre=d.querySelector('audio.tts');
    if(pre){if(pre.paused){pre.play();btn.textContent='⏸ Pausar';
        pre.onended=function(){btn.textContent='▶ Escuchar';};}
      else{pre.pause();btn.textContent='▶ Escuchar';}return;}
    var sy=window.speechSynthesis;
    if(!sy){alert('Tu navegador no soporta lectura de voz.');return;}
    if(sy.speaking||sy.pending){sy.cancel();btn.textContent='▶ Escuchar';return;}
    var t=d.getElementById('cuerpo');if(!t)return;
    btn.textContent='⏹ Detener';_cargarVoces(function(){_hablar(t.innerText,btn);});};
  // resumen del día (voz del navegador) cuando no hay MP3 pregenerado
  window.leerResumen=function(btn){var sy=window.speechSynthesis;
    if(!sy){alert('Tu navegador no soporta lectura de voz.');return;}
    if(sy.speaking||sy.pending){sy.cancel();btn.textContent='▶ Escuchar el resumen del día';return;}
    var box=d.querySelector('.claves-dia');if(!box)return;
    var intro=box.querySelector('.cd-intro'),list=box.querySelector('.cd-list');
    var txt=(intro?intro.innerText+'. ':'')+'Las claves de hoy. '+(list?list.innerText:'');
    btn.textContent='⏹ Detener';_cargarVoces(function(){_hablar(txt,btn);});};
  // compartir
  window.compartir=function(){var u=location.href,t=d.title;
    if(navigator.share)navigator.share({title:t,url:u}).catch(function(){});
    else{navigator.clipboard.writeText(u);alert('Enlace copiado');}};
  // seguir secciones + Para ti
  window.seguidas=function(){try{return JSON.parse(ls.getItem('seguidas')||'[]');}catch(e){return[];}};
  window.seguir=function(slug,el){var s=seguidas(),i=s.indexOf(slug);
    if(i<0)s.push(slug);else s.splice(i,1);ls.setItem('seguidas',JSON.stringify(s));
    if(el)el.classList.toggle('on');paraTi();};
  // --- personalización de portada: país del lector (T5) + secciones seguidas ---
  function paisSel(){return ls.getItem('pais')||'';}   // elección explícita del usuario
  var paisAuto='';                                     // país detectado por IP (fallback)
  function paisActivo(){return paisSel()||paisAuto;}
  function rankCard(c,s,pc){var r=0;
    if(pc&&(c.getAttribute('data-countries')||'').split(' ').indexOf(pc)>=0)r-=2; // país: +peso
    if(s.indexOf(c.getAttribute('data-sec'))>=0)r-=1;                              // sección seguida
    return r;}
  function ordenarPortada(){var grid=d.getElementById('masgrid');if(!grid)return;
    var s=seguidas(),pc=paisActivo(),cards=[].slice.call(grid.children);
    cards.sort(function(a,b){return rankCard(a,s,pc)-rankCard(b,s,pc);});
    cards.forEach(function(c){grid.appendChild(c);});}
  window.setPais=function(code){if(code)ls.setItem('pais',code);else ls.removeItem('pais');
    var lbl=d.getElementById('paisAuto');if(lbl&&code)lbl.textContent='';ordenarPortada();};
  function paraTi(){var box=d.getElementById('parati'),s=seguidas();
    if(box)box.style.display=s.length?'block':'none';
    d.querySelectorAll('[data-follow]').forEach(function(c){
      c.classList.toggle('on',s.indexOf(c.getAttribute('data-follow'))>=0);});
    ordenarPortada();}
  d.addEventListener('DOMContentLoaded',function(){
    paraTi();
    var sel=d.getElementById('paisSel');
    if(sel){sel.value=paisSel();sel.addEventListener('change',function(){setPais(sel.value);});}
    if(!paisSel())fetch('https://ipwho.is/').then(function(r){return r.json();})
      .then(function(j){if(j&&j.country_code){paisAuto=j.country_code.toLowerCase();ordenarPortada();
        var lbl=d.getElementById('paisAuto');
        if(lbl&&!paisSel())lbl.textContent='(detectamos: '+(j.country||j.country_code)+')';}})
      .catch(function(){});});
  // PWA
  if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(function(){});
})();
"""

TICKER_JS = r"""
(function(){
  var t=document.getElementById('tkr');if(!t)return;
  function fmt(v){return v>=1000?Math.round(v).toLocaleString('es'):(v>=100?Math.round(v):v.toFixed(2));}
  // refresco de monedas en vivo (open.er-api, gratis, con CORS, incluye CLP)
  fetch('https://open.er-api.com/v6/latest/USD')
   .then(function(r){return r.json();}).then(function(j){
     var m={clp:'CLP',brl:'BRL',mxn:'MXN'};
     Object.keys(m).forEach(function(id){var v=j.rates&&j.rates[m[id]];if(!v)return;
       document.querySelectorAll('[data-tid="'+id+'"]').forEach(function(el){
         var prev=parseFloat(el.getAttribute('data-prev'))||v;
         var val=el.querySelector('.v'),ar=el.querySelector('.a');
         if(val)val.textContent=fmt(v);
         var pct=prev?((v-prev)/prev*100):0;
         if(ar){ar.textContent=(pct>=0?'▲':'▼')+Math.abs(pct).toFixed(2)+'%';
           ar.className='a '+(pct>0?'up':(pct<0?'down':'flat'));}});});
   }).catch(function(){});
})();
"""

WEATHER_JS = r"""
(function(){
  var box=document.getElementById('wx');if(!box)return;
  var WC={0:['☀️','Despejado'],1:['🌤️','Mayormente despejado'],2:['⛅','Parcialmente nublado'],
    3:['☁️','Nublado'],45:['🌫️','Niebla'],48:['🌫️','Niebla'],51:['🌦️','Llovizna'],53:['🌦️','Llovizna'],
    55:['🌦️','Llovizna'],61:['🌧️','Lluvia'],63:['🌧️','Lluvia'],65:['🌧️','Lluvia fuerte'],66:['🌧️','Lluvia'],
    67:['🌧️','Lluvia'],71:['🌨️','Nieve'],73:['🌨️','Nieve'],75:['❄️','Nieve fuerte'],77:['❄️','Nieve'],
    80:['🌦️','Chubascos'],81:['🌦️','Chubascos'],82:['⛈️','Chubascos fuertes'],85:['🌨️','Nieve'],
    86:['❄️','Nieve'],95:['⛈️','Tormenta'],96:['⛈️','Tormenta'],99:['⛈️','Tormenta']};
  function wc(c){return WC[c]||['🌡️','—'];}
  var DIAS=['dom','lun','mar','mié','jue','vie','sáb'];
  function go(lat,lon,place){
    fetch('https://api.open-meteo.com/v1/forecast?latitude='+lat+'&longitude='+lon+
      '&current=temperature_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min'+
      '&timezone=auto&forecast_days=4')
     .then(function(r){return r.json();}).then(function(j){
       var cur=j.current,d=j.daily,w=wc(cur.weather_code),fc='';
       for(var i=1;i<4;i++){var dw=wc(d.weather_code[i]),dt=new Date(d.time[i]+'T00:00');
         fc+='<div class="wx-day"><div>'+DIAS[dt.getDay()]+'</div><div class="e">'+dw[0]+'</div>'+
             '<div class="mm">'+Math.round(d.temperature_2m_max[i])+'°</div>'+
             '<div>'+Math.round(d.temperature_2m_min[i])+'°</div></div>';}
       box.innerHTML='<div class="kicker">El tiempo</div><div class="wx-top">'+
         '<div class="wx-emoji">'+w[0]+'</div><div><div class="wx-temp">'+Math.round(cur.temperature_2m)+
         '°C</div><div class="wx-cond">'+w[1]+'</div><div class="wx-place">'+place+'</div></div></div>'+
         '<div class="wx-fc">'+fc+'</div>';
     }).catch(fail);}
  function fail(){box.innerHTML='<div class="kicker">El tiempo</div>'+
    '<div class="wx-cond" style="padding:6px 0">No pudimos obtener el clima de tu ubicación.</div>';}
  // 1) ubicación por IP (sin pedir permiso). 2) fallback: geolocalización del navegador.
  fetch('https://ipwho.is/').then(function(r){return r.json();}).then(function(j){
    if(j&&j.success!==false&&j.latitude)go(j.latitude,j.longitude,(j.city?j.city+', ':'')+(j.country||''));
    else navGeo();}).catch(navGeo);
  function navGeo(){if(navigator.geolocation)navigator.geolocation.getCurrentPosition(
    function(p){go(p.coords.latitude,p.coords.longitude,'Tu ubicación');},fail);else fail();}
})();
"""

SEARCH_JS = r"""
(function(){
  var d=document;var idx=[];var box=d.getElementById('q');var out=d.getElementById('res');
  if(!box)return;
  fetch('search-index.json').then(function(r){return r.json();}).then(function(j){idx=j;
    var qs=new URLSearchParams(location.search).get('q');if(qs){box.value=qs;run();}});
  function norm(s){return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');}
  function run(){var q=norm(box.value.trim());if(!q){out.innerHTML='';return;}
    var terms=q.split(/\s+/);
    var scored=idx.map(function(a){var hay=norm(a.title+' '+a.subtitle+' '+a.text+' '+(a.tags||[]).join(' '));
      var sc=0;terms.forEach(function(t){if(a.title&&norm(a.title).indexOf(t)>=0)sc+=3;
        var m=hay.split(t).length-1;sc+=m;});return{a:a,sc:sc};})
      .filter(function(x){return x.sc>0;}).sort(function(x,y){return y.sc-x.sc;}).slice(0,20);
    if(!scored.length){out.innerHTML='<p class="meta">Sin resultados para “'+box.value+'”.</p>';return;}
    out.innerHTML=scored.map(function(x){var a=x.a;return '<div class="wn-item"><span class="kicker">'+a.sectionName+
      '</span><div class="t"><a href="'+a.url+'">'+a.title+'</a></div><div class="meta">'+a.dateLong+'</div>'+
      '<p class="dek">'+a.subtitle+'</p></div>';}).join('');}
  box.addEventListener('input',run);
})();
"""

ASK_JS = r"""
(function(){
  var d=document, idx=null;
  function norm(s){return (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');}
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function loadIdx(cb){ if(idx){cb();return;}
    fetch('/search-index.json').then(function(r){return r.json();}).then(function(j){idx=j;cb();}).catch(function(){idx=[];cb();}); }
  function relInternos(q){ var terms=norm(q).split(/\s+/).filter(function(t){return t.length>=3;});
    return (idx||[]).map(function(a){var hay=norm(a.title+' '+a.subtitle+' '+a.text+' '+(a.tags||[]).join(' '));
      var sc=0;terms.forEach(function(t){sc+=hay.split(t).length-1;if(norm(a.title).indexOf(t)>=0)sc+=3;});return {a:a,sc:sc};})
      .filter(function(x){return x.sc>0;}).sort(function(x,y){return y.sc-x.sc;}).slice(0,4)
      .map(function(x){return {title:x.a.title,url:'/'+x.a.url,section:x.a.sectionName||x.a.section,date:x.a.dateLong||x.a.date};}); }
  function tarjetas(rel){ if(!rel||!rel.length)return '';
    return '<div class="ask-rel"><h4>En Análisis.com</h4>'+rel.map(function(r){
      return '<a class="ask-card" href="'+r.url+'"><span class="kicker">'+esc(r.section)+'</span>'+esc(r.title)+'</a>';}).join('')+'</div>'; }
  function fuentes(src){ if(!src||!src.length)return '';
    return '<div class="ask-src"><h4>Fuentes</h4>'+src.map(function(s){var dom='';try{dom=new URL(s.url).hostname.replace(/^www\./,'');}catch(e){}
      return '<a href="'+esc(s.url)+'" target="_blank" rel="noopener"><span class="ask-dom">'+esc(dom)+'</span> '+esc(s.title)+'</a>';}).join('')+'</div>'; }
  function respuesta(text){ text=(text||'').replace(/\*\*/g,'');
    var lines=text.split(/\n+/).map(function(s){return s.trim();}).filter(Boolean);
    var html='',inList=false;
    lines.forEach(function(l){ var m=/^[-*•]\s+(.*)/.exec(l);
      if(m){ if(!inList){html+='<ul>';inList=true;} html+='<li>'+esc(m[1])+'</li>'; }
      else { if(inList){html+='</ul>';inList=false;} html+='<p>'+esc(l)+'</p>'; } });
    if(inList)html+='</ul>';
    return '<div class="ask-ans">'+html+'</div>'; }
  var AVISO='<p class="meta ask-note">Respuesta generada con IA.</p>';
  function interno(out,q){ loadIdx(function(){ var rel=relInternos(q);
    if(!rel.length){out.innerHTML='<div class="ask-ans"><p>No encuentro nada en el archivo de Análisis.com sobre eso todavía.</p></div>';return;}
    out.innerHTML='<div class="ask-ans"><p>Esto es lo que ha publicado Análisis.com al respecto:</p></div>'+tarjetas(rel)
      +'<p class="meta ask-note">Respuestas ampliadas con IA y búsqueda web cuando el asistente esté conectado.</p>'; }); }
  function preguntar(box,q){ var out=box.querySelector('.ask-out'); if(!out)return; q=(q||'').trim(); if(!q)return;
    out.innerHTML='<p class="ask-loading">Buscando en Análisis y en la web… (unos segundos)</p>';
    if(window.ANALISIS_ASK_URL){
      var ctrl=new AbortController(), to=setTimeout(function(){ctrl.abort();},28000);
      fetch(window.ANALISIS_ASK_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:q}),signal:ctrl.signal})
        .then(function(r){return r.json();}).then(function(j){ clearTimeout(to);
          if(!j||j.degrade||!j.answer){interno(out,q);return;}
          out.innerHTML=respuesta(j.answer)+tarjetas(j.related)+AVISO;
        }).catch(function(){clearTimeout(to);interno(out,q);});
      return; }
    interno(out,q); }
  window.preguntar=function(){var b=d.querySelector('.ask');if(b)preguntar(b,(b.querySelector('.ask-q')||{}).value);};
  d.querySelectorAll('.ask').forEach(function(box){
    var inp=box.querySelector('.ask-q'), go=box.querySelector('.ask-go');
    if(go)go.addEventListener('click',function(){preguntar(box,inp&&inp.value);});
    if(inp)inp.addEventListener('keydown',function(e){if(e.key==='Enter')preguntar(box,inp.value);});
    box.querySelectorAll('.ask-chip').forEach(function(c){c.addEventListener('click',function(){
      if(inp)inp.value=c.textContent;preguntar(box,c.textContent);});});
  });
})();
"""

# Diccionario de INTERFAZ (chrome) es -> {en, pt, de}. El contenido de las notas
# se traduce aparte con IA (endpoint /api/translate). Multi-idioma (T-idiomas).
I18N = {
    "Contexto que importa. Noticias del mundo, analizadas.":
        {"en": "Context that matters. World news, analyzed.",
         "pt": "Contexto que importa. Notícias do mundo, analisadas.",
         "de": "Kontext, der zählt. Weltnachrichten, analysiert."},
    "Buscar": {"en": "Search", "pt": "Buscar", "de": "Suchen"},
    "Datos": {"en": "Data", "pt": "Dados", "de": "Daten"},
    "Portada": {"en": "Home", "pt": "Início", "de": "Startseite"},
    "Archivo": {"en": "Archive", "pt": "Arquivo", "de": "Archiv"},
    "Tecnología": {"en": "Technology", "pt": "Tecnologia", "de": "Technologie"},
    "Economía": {"en": "Economy", "pt": "Economia", "de": "Wirtschaft"},
    "Minería": {"en": "Mining", "pt": "Mineração", "de": "Bergbau"},
    "Agricultura": {"en": "Agriculture", "pt": "Agricultura", "de": "Landwirtschaft"},
    "Retail": {"en": "Retail", "pt": "Varejo", "de": "Einzelhandel"},
    "Banca": {"en": "Banking", "pt": "Bancos", "de": "Banken"},
    "Energía y Medioambiente": {"en": "Energy & Environment",
        "pt": "Energia e meio ambiente", "de": "Energie & Umwelt"},
    "Mercados y Cripto": {"en": "Markets & Crypto",
        "pt": "Mercados e cripto", "de": "Märkte & Krypto"},
    "Internacional": {"en": "International", "pt": "Internacional", "de": "International"},
    "Startups": {"en": "Startups", "pt": "Startups", "de": "Startups"},
    "Boletín": {"en": "Newsletter", "pt": "Boletim", "de": "Newsletter"},
    "Asistente": {"en": "Assistant", "pt": "Assistente", "de": "Assistent"},
    "Correcciones": {"en": "Corrections", "pt": "Correções", "de": "Korrekturen"},
    "Pregúntale a Análisis": {"en": "Ask Análisis", "pt": "Pergunte ao Análisis",
        "de": "Frag Análisis"},
    "Respuesta elaborada con lo publicado + la web":
        {"en": "Answer built from our articles + the web",
         "pt": "Resposta elaborada com o publicado + a web",
         "de": "Antwort aus unseren Artikeln + dem Web"},
    "Las 5 claves de hoy": {"en": "Today's 5 key points",
        "pt": "As 5 chaves de hoje", "de": "Die 5 wichtigsten Punkte heute"},
    "Más noticias": {"en": "More news", "pt": "Mais notícias", "de": "Weitere Nachrichten"},
    "Prioriza tu país y las secciones que sigas":
        {"en": "Prioritizes your country and the sections you follow",
         "pt": "Prioriza seu país e as seções que você segue",
         "de": "Priorisiert dein Land und deine Rubriken"},
    "Lo último": {"en": "Latest", "pt": "Últimas", "de": "Neueste"},
    "El tiempo": {"en": "Weather", "pt": "O tempo", "de": "Wetter"},
    "▶ Escuchar el resumen del día": {"en": "▶ Listen to today's briefing",
        "pt": "▶ Ouvir o resumo do dia", "de": "▶ Tagesüberblick anhören"},
    "¿Cómo va el precio del cobre?": {"en": "How is the copper price?",
        "pt": "Como está o preço do cobre?", "de": "Wie steht der Kupferpreis?"},
    "¿Qué pasa con las tasas en la región?":
        {"en": "What's happening with rates in the region?",
         "pt": "O que acontece com as taxas na região?",
         "de": "Was passiert mit den Zinsen in der Region?"},
    "¿Últimas noticias del litio?": {"en": "Latest lithium news?",
        "pt": "Últimas notícias do lítio?", "de": "Neueste Lithium-Nachrichten?"},
    "Preguntar": {"en": "Ask", "pt": "Perguntar", "de": "Fragen"},
    "Pregunta cualquier cosa: ¿cómo va el cobre? ¿y las tasas en la región?":
        {"en": "Ask anything: how's copper? and rates in the region?",
         "pt": "Pergunte qualquer coisa: como está o cobre? e as taxas na região?",
         "de": "Frag alles: Wie steht Kupfer? und die Zinsen in der Region?"},
    "Relacionadas": {"en": "Related", "pt": "Relacionadas", "de": "Verwandte"},
    "Claves en 30 segundos": {"en": "Key points in 30 seconds",
        "pt": "Chaves em 30 segundos", "de": "Das Wichtigste in 30 Sekunden"},
    "Preguntas frecuentes": {"en": "FAQ", "pt": "Perguntas frequentes",
        "de": "Häufige Fragen"},
    "¿Qué te pareció?": {"en": "What did you think?", "pt": "O que você achou?",
        "de": "Was denkst du?"},
    "👍 Interesante": {"en": "👍 Interesting", "pt": "👍 Interessante", "de": "👍 Interessant"},
    "🔥 Importante": {"en": "🔥 Important", "pt": "🔥 Importante", "de": "🔥 Wichtig"},
    "🤔 Me hace pensar": {"en": "🤔 Makes me think", "pt": "🤔 Faz pensar",
        "de": "🤔 Regt zum Nachdenken an"},
    "😮 Sorprendente": {"en": "😮 Surprising", "pt": "😮 Surpreendente", "de": "😮 Überraschend"},
    "▶ Escuchar": {"en": "▶ Listen", "pt": "▶ Ouvir", "de": "▶ Anhören"},
    "Compartir": {"en": "Share", "pt": "Compartilhar", "de": "Teilen"},
    "Política de correcciones": {"en": "Corrections policy",
        "pt": "Política de correções", "de": "Korrekturrichtlinie"},
    "Encuesta": {"en": "Poll", "pt": "Enquete", "de": "Umfrage"},
}

I18N_JS = r"""
(function(){
  var d=document, ls=window.localStorage, DICT=__I18N__;
  var CH='.sub, a.tb, nav.main a, .section-head h2, .section-head .d, .ask-chip, .ask-go, .cd-listen, .claves h4, .faq h4, .react-q, .react button, .poll h4, .byline .acts button, .trust a, .kicker, footer.site a';
  var CT='.lead-main h1 a, .lead-main .dek, .card h3, .card .dek, .wn-item .t a, article.post h1, article.post .dek, .claves li, #cuerpo p, .faq details summary, .faq details>p, .it .t a, .it .dek';
  var detected=null;
  function want(){ return ls.getItem('lang') || detected || 'es'; }
  function hsh(s){var h=5381,i=s.length;while(i)h=(h*33)^s.charCodeAt(--i);return (h>>>0).toString(36);}
  function detect(cc){cc=(cc||'').toLowerCase();
    if(cc==='br')return 'pt';
    if(['de','at','ch','li'].indexOf(cc)>=0)return 'de';
    if(['us','gb','ca','au','ie','nz','in','za','ng','ph','sg'].indexOf(cc)>=0)return 'en';
    return 'es';}
  function chrome(lang){
    d.querySelectorAll(CH).forEach(function(el){ if(el.children.length)return;
      var o=el.getAttribute('data-o'); if(o==null){o=el.textContent.trim(); if(!DICT[o])return; el.setAttribute('data-o',o);}
      el.textContent=(lang==='es')?o:((DICT[o]||{})[lang]||o); });
    d.querySelectorAll('.ask-q').forEach(function(el){var o=el.getAttribute('data-po');
      if(o==null){o=el.getAttribute('placeholder')||''; if(!DICT[o])return; el.setAttribute('data-po',o);}
      el.setAttribute('placeholder',(lang==='es')?o:((DICT[o]||{})[lang]||o));});
    var b=d.getElementById('langbtn'); if(b)b.textContent='🌐 '+lang.toUpperCase();
    d.documentElement.setAttribute('lang',lang);}
  function content(lang){
    var els=[].slice.call(d.querySelectorAll(CT)).filter(function(el){return el.textContent.trim();}).slice(0,60);
    if(!els.length)return;
    els.forEach(function(el){if(el.getAttribute('data-co')==null)el.setAttribute('data-co',el.textContent);});
    if(lang==='es'){els.forEach(function(el){el.textContent=el.getAttribute('data-co');});return;}
    var texts=els.map(function(el){return el.getAttribute('data-co');});
    var ck='trc:'+lang+':'+hsh(texts.join(''));
    var cached=null;try{cached=JSON.parse(ls.getItem(ck));}catch(e){}
    function apply(arr){els.forEach(function(el,i){if(arr[i]!=null)el.textContent=arr[i];});}
    if(cached&&cached.length===els.length){apply(cached);return;}
    if(!window.ANALISIS_ASK_URL)return;
    var url=window.ANALISIS_ASK_URL.replace(/\/api\/ask$/,'/api/translate');
    fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({texts:texts,lang:lang})})
      .then(function(r){return r.json();}).then(function(j){
        if(j&&j.t&&j.t.length===els.length){apply(j.t);try{ls.setItem(ck,JSON.stringify(j.t));}catch(e){}}}).catch(function(){});}
  function apply(lang){chrome(lang);content(lang);}
  window.setLang=function(lang){if(['es','en','pt','de'].indexOf(lang)<0)return;ls.setItem('lang',lang);var m=d.getElementById('langmenu');if(m)m.hidden=true;apply(lang);};
  d.addEventListener('DOMContentLoaded',function(){
    var btn=d.getElementById('langbtn'), menu=d.getElementById('langmenu');
    if(btn&&menu){btn.addEventListener('click',function(e){e.stopPropagation();menu.hidden=!menu.hidden;});
      menu.querySelectorAll('[data-lang]').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();setLang(a.getAttribute('data-lang'));});});
      d.addEventListener('click',function(){menu.hidden=true;});}
    apply(want());
    if(!ls.getItem('lang'))fetch('https://ipwho.is/').then(function(r){return r.json();}).then(function(j){
      if(j&&j.country_code){var dl=detect(j.country_code);if(dl!=='es'&&!ls.getItem('lang')){detected=dl;apply(dl);}}}).catch(function(){});
  });
})();
"""

DATOS_JS = r"""
(function(){
  var d=document;var host=d.getElementById('charts');if(!host)return;
  var src=window.__DATA__?Promise.resolve(window.__DATA__):fetch('data.json').then(function(r){return r.json();});
  src.then(function(j){
    d.getElementById('dupd').textContent='Datos al '+j.updated;
    var dark=d.documentElement.getAttribute('data-tema')==='oscuro';
    var col=dark?'#e9eaec':'#111417',grid=dark?'#2a2d31':'#e2e2e0';
    j.series.forEach(function(s){
      var wrap=d.createElement('div');wrap.className='dcard';
      wrap.innerHTML='<div class="kicker">'+s.group+'</div><h3 style="margin:.2em 0 .4em">'+s.name+
        ' <span class="meta">('+s.unit+')</span></h3><canvas></canvas>';
      host.appendChild(wrap);
      new Chart(wrap.querySelector('canvas'),{type:'line',
        data:{labels:s.points.map(function(p){return p[0];}),
          datasets:[{data:s.points.map(function(p){return p[1];}),borderColor:'#c00000',
            backgroundColor:'rgba(192,0,0,.08)',fill:true,tension:.3,pointRadius:2}]},
        options:{plugins:{legend:{display:false}},
          scales:{x:{ticks:{color:col},grid:{color:grid}},y:{ticks:{color:col},grid:{color:grid}}}}});});
    var rt=d.getElementById('rates');if(rt&&j.rates){rt.innerHTML=
      '<tr><th>Banco central</th><th>Tasa</th><th>Sesgo</th></tr>'+
      j.rates.map(function(r){return '<tr><td>'+r.pais+'</td><td>'+r.tasa.toFixed(2)+'%</td><td>'+r.sesgo+'</td></tr>';}).join('');}
    // --- conversor de divisas (rates en vivo, con respaldo del tablero) ---
    var MON=['USD','CLP','BRL','MXN','ARS','COP','PEN','EUR'];
    var rates={USD:1};
    (j.series||[]).forEach(function(s){var m={clp:'CLP',brl:'BRL',mxn:'MXN'}[s.id];
      if(m)rates[m]=s.points[s.points.length-1][1];});
    var from=d.getElementById('cv-from'),to=d.getElementById('cv-to'),
        amt=d.getElementById('cv-amt'),cvout=d.getElementById('cv-out'),cvsrc=d.getElementById('cv-src');
    if(from&&to){MON.forEach(function(m){from.innerHTML+='<option>'+m+'</option>';to.innerHTML+='<option>'+m+'</option>';});
      from.value='USD';to.value='CLP';
      function conv(){var a=parseFloat(amt.value)||0,rf=rates[from.value],rt2=rates[to.value];
        if(!rf||!rt2){cvout.textContent='—';return;}
        var v=a*(rt2/rf);
        cvout.textContent=a.toLocaleString('es')+' '+from.value+' = '+
          v.toLocaleString('es',{maximumFractionDigits:2})+' '+to.value;}
      [amt,from,to].forEach(function(el){el.addEventListener('input',conv);});
      fetch('https://open.er-api.com/v6/latest/USD').then(function(r){return r.json();}).then(function(x){
        if(x&&x.rates){MON.forEach(function(m){if(x.rates[m])rates[m]=x.rates[m];});
          if(cvsrc)cvsrc.textContent='Tipo de cambio en vivo';}conv();}).catch(function(){
          if(cvsrc)cvsrc.textContent='Tipo de cambio del tablero (sin conexión)';conv();});
      conv();}
    // --- calculadora de commodities (último valor del tablero) ---
    var comm=(j.series||[]).filter(function(s){return (s.unit||'').indexOf('US$')===0;});
    var cs=d.getElementById('cc-serie'),qty=d.getElementById('cc-qty'),ccout=d.getElementById('cc-out');
    if(cs){comm.forEach(function(s,i){cs.innerHTML+='<option value="'+i+'">'+s.name+' ('+s.unit+')</option>';});
      function calc(){var s=comm[cs.value|0];if(!s)return;var q=parseFloat(qty.value)||0,
        price=s.points[s.points.length-1][1],tot=q*price;
        ccout.textContent=q.toLocaleString('es')+' × '+price+' '+s.unit+' = US$ '+
          tot.toLocaleString('es',{maximumFractionDigits:2});}
      [qty,cs].forEach(function(el){el.addEventListener('input',calc);});calc();}
  });
})();
"""

ART_CHART_JS = (
    "(function(){var c=document.getElementById('artchart');"
    "if(!c||!window.Chart||!window.__SERIE__)return;var s=window.__SERIE__;"
    "var dark=document.documentElement.getAttribute('data-tema')==='oscuro';"
    "var col=dark?'#e9eaec':'#111417';"
    "new Chart(c,{type:'line',data:{labels:s.points.map(function(p){return p[0];}),"
    "datasets:[{data:s.points.map(function(p){return p[1];}),borderColor:'#c00000',"
    "backgroundColor:'rgba(192,0,0,.08)',fill:true,tension:.3,pointRadius:2}]},"
    "options:{plugins:{legend:{display:false}},maintainAspectRatio:false,"
    "scales:{x:{ticks:{color:col}},y:{ticks:{color:col}}}}});})();")

REACT_JS = r"""
(function(){var d=document,ls=window.localStorage;
  // Reacciones: una por nota (se puede cambiar/quitar). Estado en localStorage.
  d.querySelectorAll('.react').forEach(function(box){
    var aid=box.getAttribute('data-aid'),key='react:'+aid,saved=ls.getItem(key);
    box.querySelectorAll('button').forEach(function(b){
      if(saved===b.getAttribute('data-r'))b.classList.add('on');
      b.addEventListener('click',function(){
        var r=b.getAttribute('data-r');
        box.querySelectorAll('button').forEach(function(x){x.classList.remove('on');});
        if(saved===r){ls.removeItem(key);saved=null;return;}
        b.classList.add('on');ls.setItem(key,r);saved=r;
        if(window.gtag)gtag('event','reaccion',{article_id:aid,tipo:r});
      });
    });
  });
  // Encuesta: un voto por navegador; tras votar se bloquea.
  d.querySelectorAll('.poll').forEach(function(box){
    var aid=box.getAttribute('data-aid'),key='poll:'+aid,saved=ls.getItem(key);
    var thanks=box.querySelector('.poll-thanks');
    var btns=box.querySelectorAll('.poll-opts button');
    btns.forEach(function(b){
      if(saved===b.getAttribute('data-i')){b.classList.add('on');if(thanks)thanks.hidden=false;}
      b.addEventListener('click',function(){
        if(ls.getItem(key)!==null)return;
        var i=b.getAttribute('data-i');
        b.classList.add('on');ls.setItem(key,i);if(thanks)thanks.hidden=false;
        btns.forEach(function(x){x.disabled=true;});
        if(window.gtag)gtag('event','encuesta_voto',{article_id:aid,opcion:i});
      });
    });
    if(saved!==null)btns.forEach(function(x){x.disabled=true;});
  });
})();
"""

SW_JS = r"""
const C='analisis-__SWVER__';
self.addEventListener('install',e=>{self.skipWaiting();
  e.waitUntil(caches.open(C).then(c=>c.addAll(['/','/index.html','/assets/app.css','/assets/app.js'])));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(
  k.filter(x=>x!==C).map(x=>caches.delete(x)))));self.clients.claim();});
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;
  var req=e.request,esHTML=req.mode==='navigate'||(req.headers.get('accept')||'').indexOf('text/html')>=0;
  if(esHTML){ // network-first: páginas siempre frescas online, respaldo offline
    e.respondWith(fetch(req).then(res=>{var cp=res.clone();caches.open(C).then(c=>c.put(req,cp));return res;})
      .catch(()=>caches.match(req).then(r=>r||caches.match('/index.html'))));return;}
  // cache-first para assets (la caché se versiona con C en cada build)
  e.respondWith(caches.match(req).then(r=>r||fetch(req).then(res=>{
    var cp=res.clone();caches.open(C).then(c=>c.put(req,cp));return res;}).catch(()=>r)));});
"""

FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">'
           '<rect width="120" height="120" rx="26" fill="#ffffff"/>'
           '<circle cx="60" cy="60" r="44" fill="none" stroke="#241a9c" stroke-width="12" '
           'stroke-linecap="round" stroke-dasharray="203 277" transform="rotate(-20 60 60)"/>'
           '<circle cx="60" cy="60" r="30" fill="none" stroke="#3f2be6" stroke-width="11" '
           'stroke-linecap="round" stroke-dasharray="131 189" transform="rotate(120 60 60)"/>'
           '<circle cx="60" cy="60" r="17" fill="none" stroke="#ec1414" stroke-width="10" '
           'stroke-linecap="round" stroke-dasharray="68 107" transform="rotate(240 60 60)"/></svg>')

# Símbolo animado de la marca (los anillos giran vía CSS: .brand .mark). Reutilizado
# en la cabecera y el footer.
MARK_SVG = ('<svg class="mark" viewBox="0 0 120 120" role="img" aria-hidden="true">'
            '<circle class="r1" cx="60" cy="60" r="47" fill="none" stroke-width="12" stroke-linecap="round" stroke-dasharray="213 296"></circle>'
            '<circle class="r2" cx="60" cy="60" r="32" fill="none" stroke-width="11" stroke-linecap="round" stroke-dasharray="140 201"></circle>'
            '<circle class="r3" cx="60" cy="60" r="18" fill="none" stroke-width="10" stroke-linecap="round" stroke-dasharray="72 113"></circle>'
            '</svg>')

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?'
         'family=Source+Serif+4:opsz,wght@8..60,400;8..60,700;8..60,800;8..60,900&'
         'family=Libre+Franklin:wght@400;600;700&display=swap" rel="stylesheet">')


def build_ticker():
    """Franja de datos incrustada (funciona sin fetch, incluso en file://).
    Las monedas se refrescan en vivo con TICKER_JS."""
    if not os.path.exists(DATA):
        return ""
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)

    def fmt(v):
        if v >= 1000:
            return f"{v:,.0f}".replace(",", ".")
        if v >= 100:
            return f"{v:.0f}"
        return f"{v:.2f}"

    items = ['<span style="display:inline-block;width:20px"></span>']
    for s in d.get("series", []):
        pts = s["points"]
        last = pts[-1][1]
        prev = pts[-2][1] if len(pts) > 1 else last
        pct = ((last - prev) / prev * 100) if prev else 0
        cls = "up" if pct > 0 else ("down" if pct < 0 else "flat")
        arrow = ("▲" if pct > 0 else ("▼" if pct < 0 else "■")) + f"{abs(pct):.1f}%"
        es_moneda = s.get("group") == "Monedas"
        label = s["id"].upper() if es_moneda else s["name"]
        attr = f' data-tid="{s["id"]}" data-prev="{prev}"' if es_moneda else ""
        items.append(
            f'<span class="tk"{attr}><b>{escape(label)}</b> '
            f'<span class="v">{fmt(last)}</span> '
            f'<span style="color:#8a93a0">{escape(s["unit"])}</span> '
            f'<span class="a {cls}">{arrow}</span></span>')
    inner = "".join(items)
    return ('<div class="ticker" aria-label="Datos de mercado">'
            '<div class="ticker-lbl">MERCADOS · EN VIVO</div>'
            f'<div class="ticker-vp"><div class="ticker-track" id="tkr">{inner}{inner}</div></div></div>')


def analytics_tag():
    tags = []
    if ANALYTICS_DOMAIN:
        tags.append(f'<script defer data-domain="{ANALYTICS_DOMAIN}" '
                    f'src="https://plausible.io/js/script.js"></script>')
    if GA4_ID:
        tags.append(
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>'
            f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
            f'gtag("js",new Date());gtag("config","{GA4_ID}");</script>')
    if ASK_URL:
        tags.append(f'<script>window.ANALISIS_ASK_URL="{ASK_URL}";</script>')
    return "".join(tags)


def head(title, active="", depth=0, description="", image="", ld=None, extra_js=""):
    base = "../" * depth
    hoy = fecha_larga(datetime.now().strftime("%Y-%m-%d"))
    desc = description or SITE["tagline"]
    ogimg = image or f"{SITE_URL}/img/{list(COVER.values())[0]}" if COVER else ""
    links = "".join(
        f'<a class="{ "active" if s["slug"]==active else "" }" '
        f'href="{base}seccion/{s["slug"]}.html">{escape(s["name"])}</a>'
        for s in SECTIONS)
    ldjson = ""
    if ld:
        ldjson = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<meta property="og:type" content="website"><meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}"><meta property="og:image" content="{escape(ogimg)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{base}favicon.svg"><link rel="manifest" href="{base}manifest.webmanifest">
<meta name="theme-color" content="#111417">
{FONTS}<link rel="stylesheet" href="{base}assets/app.css?v={ASSET_VER}">
{ldjson}{analytics_tag()}
</head><body>
{'<div class="progress"></div>' if active=='_article' else ''}
<header class="site"><div class="wrap">
  <div class="strip">
    <span>{escape(hoy.capitalize())}</span>
    <span class="tools">
      <a class="tb" href="{base}buscar.html">Buscar</a>
      <a class="tb" href="{base}panel.html">LogIn</a>
      <a class="tb" href="{base}datos.html">Datos</a>
      <span class="langwrap"><button class="tb" id="langbtn" type="button" title="Idioma / Language">🌐 ES</button>
        <div class="langmenu" id="langmenu" hidden>
          <a href="#" data-lang="es">Español</a><a href="#" data-lang="en">English</a>
          <a href="#" data-lang="pt">Português</a><a href="#" data-lang="de">Deutsch</a>
        </div></span>
      <button onclick="fuente(-1)" title="Reducir texto">A-</button>
      <button onclick="fuente(1)" title="Aumentar texto">A+</button>
      <button onclick="toggleTema()" title="Modo claro/oscuro">◐</button>
    </span>
  </div>
  <div class="masthead">
    <a href="{base}index.html" class="brand" aria-label="analisis.com — inicio">{MARK_SVG}<span class="wm">analisis.com</span></a>
    <div class="sub">{escape(SITE['tagline'])}</div>
  </div>
</div>
<nav class="main"><div class="wrap">
  <a href="{base}index.html">Portada</a>{links}<a href="{base}archivo.html">Archivo</a>
</div></nav>
{TICKER_HTML}
</header>
<main class="wrap">"""


def foot(depth=0, extra_js=""):
    base = "../" * depth
    y = datetime.now().year
    js = f'<script src="{base}assets/app.js?v={ASSET_VER}"></script>'
    if extra_js:
        js += f'<script>{extra_js}</script>'
    return f"""</main>
<footer class="site"><div class="wrap">
  <a href="{base}index.html" class="brand brand-foot" aria-label="analisis.com — inicio">{MARK_SVG}<span class="wm">analisis.com</span></a>
  <div class="foot-tag">{escape(SITE['tagline'])}</div>
  Artículos originales a partir del contraste de múltiples fuentes internacionales.
  Actualización cada 24 h. ·
  <a href="{base}boletin/index.html">Boletín</a> ·
  <a href="{base}datos.html">Datos</a> ·
  <a href="{base}asistente.html">Asistente</a> ·
  <a href="{base}correcciones.html">Correcciones</a> ·
  <a href="{base}rss.xml">RSS</a><br>
  © {y} {escape(SITE['domain'])}. Portadas propias o con licencia libre, atribuidas a su autor.
</div></footer>
{js}
</body></html>"""


def img_path(a, base):
    return f"{base}img/{COVER[a['id']]}"


def alt_for(a):
    return escape(a.get("image_alt") or a["title"])


def _paises(a):
    """Códigos de país de una nota: usa el campo guardado o lo calcula al vuelo."""
    if "countries" in a:
        return a["countries"]
    return paises_de(a.get("title", "") + " " + a.get("subtitle", "") + " "
                     + " ".join(a.get("body", [])) + " " + " ".join(a.get("tags", [])))


def card(a, depth=1, placeholder=False):
    base = "../" * depth
    sec = SECTION_BY_SLUG[a["section"]]
    if placeholder:
        src = f"{base}img/section-{a['section']}.svg"
        return (f'<a class="card placeholder" data-sec="{a["section"]}" href="#">'
                f'<div class="thumb"><img src="{src}" alt=""></div>'
                f'<span class="kicker">{escape(sec["name"])}</span><h3>{escape(a["title"])}</h3>'
                f'<span class="badge">Ejemplo — se generará automáticamente</span></a>')
    return (f'<a class="card" data-sec="{a["section"]}" '
            f'data-countries="{" ".join(_paises(a))}" href="{base}articulo/{a["id"]}.html">'
            f'<div class="thumb"><img src="{img_path(a, base)}" alt="{alt_for(a)}"></div>'
            f'<span class="kicker">{escape(sec["name"])}</span><h3>{escape(a["title"])}</h3>'
            f'<p class="dek">{escape(a["subtitle"])}</p>'
            f'<div class="meta">{fecha_larga(a["date"])} · {reading_time(a)} min</div></a>')


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def write_covers(arts):
    os.makedirs(IMGDIR, exist_ok=True)
    os.makedirs(COVERS_DIR, exist_ok=True)
    for a in arts:
        # Query de imagen: prioriza el image_query seguro que redacta el pipeline;
        # si no existe (notas antiguas), usa tags; y ancla SIEMPRE con la sección.
        base = a.get("image_query") or " ".join((a.get("tags") or [])[:2])
        query = f"{base} {SECTION_VISUAL.get(a['section'], a['section'])}".strip()
        fn, credito = build_cover(seed=a["id"], section=a["section"],
                                  prompt=a.get("image_prompt", ""),
                                  imgdir=COVERS_DIR, basename=f"article-{a['id']}",
                                  query=query)
        COVER[a["id"]] = fn
        if credito:
            CREDIT[a["id"]] = credito
        shutil.copy(os.path.join(COVERS_DIR, fn), os.path.join(IMGDIR, fn))
    for s in SECTIONS:
        write(os.path.join(IMGDIR, f"section-{s['slug']}.svg"),
              cover_svg(f"section-{s['slug']}", s["slug"]))


def write_audio(arts):
    """Voz neuronal por nota: usa el MP3 cacheado/generado si existe (si no,
    el sitio usa la voz del navegador). Ver generator/audio.py."""
    for a in arts:
        fn = build_audio(a, audiodir=AUDIO_DIR, basename=f"article-{a['id']}")
        if fn:
            AUDIO[a["id"]] = fn
            os.makedirs(AUDIO_OUT, exist_ok=True)
            shutil.copy(os.path.join(AUDIO_DIR, fn), os.path.join(AUDIO_OUT, fn))


def write_briefing(arts):
    """Briefing de audio del día (podcast corto del resumen + las 5 claves). Usa
    el MP3 cacheado/generado si AUDIO_TTS y clave; si no, deja BRIEFING en None y
    la portada ofrece la voz del navegador. Ver generator/audio.py."""
    global BRIEFING
    claves = _claves_hoy(arts)
    if not claves:
        return
    fecha = claves[0]["date"]
    intro = _digest_intro(fecha)
    partes = [f"Resumen de Análisis punto com para el {fecha_larga(fecha)}."]
    if intro:
        partes.append(intro)
    partes.append("Estas son las claves de hoy.")
    for a in claves:
        partes.append(a["title"] + ". " + (a.get("subtitle") or ""))
    fn = build_briefing("\n\n".join(partes),
                        audiodir=AUDIO_DIR, basename=f"briefing-{fecha}")
    if fn:
        BRIEFING = fn
        os.makedirs(AUDIO_OUT, exist_ok=True)
        shutil.copy(os.path.join(AUDIO_DIR, fn), os.path.join(AUDIO_OUT, fn))


# ---- temas (entidades) a partir de tags ----
def build_temas(arts):
    temas = {}
    for a in arts:
        for t in a.get("tags", []):
            temas.setdefault(slugify(t), {"name": t, "arts": []})["arts"].append(a)
    return temas


def _empresas(a):
    """Slugs de empresas de una nota: usa el campo guardado o lo calcula al vuelo."""
    if "companies" in a:
        return a["companies"]
    return empresas_de(a.get("title", "") + " " + a.get("subtitle", "") + " "
                       + " ".join(a.get("body", [])) + " " + " ".join(a.get("tags", [])))


def _serie_seccion(section):
    """Serie de datos (data.json) asociada a una sección, o None (T11)."""
    return SERIES_BY_ID.get(SECTION_SERIE.get(section, ""))


def build_hubs(arts):
    """Agrupa notas por PAÍS y por EMPRESA/entidad para las páginas hub (T9).
    Devuelve dos dicts slug -> {name, arts}."""
    paises, empresas = {}, {}
    for a in arts:
        for code in _paises(a):
            nombre = PAIS_NOMBRE.get(code, code.upper())
            paises.setdefault(slugify(nombre),
                              {"name": nombre, "arts": []})["arts"].append(a)
        for slug in _empresas(a):
            empresas.setdefault(slug,
                                {"name": EMPRESAS[slug]["name"], "arts": []})["arts"].append(a)
    return paises, empresas


def _hub_pages(grupos, carpeta, etiqueta):
    """Escribe una página hub (línea de tiempo) por país o empresa."""
    for slug, g in grupos.items():
        arts_h = sorted(g["arts"], key=lambda x: x["date"], reverse=True)
        h = head(f"{g['name']} — {etiqueta} — {SITE['name']}", depth=1,
                 description=f"Toda la cobertura de Análisis.com sobre {g['name']}.")
        h += (f'<div class="section-head"><h2>{escape(etiqueta)}: {escape(g["name"])}</h2>'
              f'<span class="d">Cobertura y línea de tiempo · {len(arts_h)} nota'
              f'{"s" if len(arts_h) != 1 else ""}</span></div>')
        h += '<div class="tl">'
        for a in arts_h:
            sec = SECTION_BY_SLUG[a["section"]]
            h += (f'<div class="it"><span class="kicker">{escape(sec["name"])} · '
                  f'{fecha_larga(a["date"])}</span>'
                  f'<div class="wn-item" style="border:0;padding-top:2px">'
                  f'<div class="t"><a href="../articulo/{a["id"]}.html">{escape(a["title"])}</a></div>'
                  f'<p class="dek">{escape(a["subtitle"])}</p></div></div>')
        h += '</div>' + foot(1)
        write(os.path.join(OUT, carpeta, f"{slug}.html"), h)


def article_ld(a):
    sec = SECTION_BY_SLUG[a["section"]]
    url = f"{SITE_URL}/articulo/{a['id']}.html"
    fecha = a.get("updated") or a["date"]
    noticia = {
        "@type": "NewsArticle",
        "headline": a["title"], "description": a.get("lead") or a["subtitle"],
        "datePublished": fecha, "dateModified": fecha,
        "articleSection": sec["name"], "inLanguage": "es",
        "keywords": ", ".join(a.get("tags", [])),
        "wordCount": sum(len(p.split()) for p in a.get("body", [])),
        "image": [f"{SITE_URL}/img/{COVER[a['id']]}"],
        "author": {"@type": "Organization", "name": "Análisis.com", "url": SITE_URL},
        "publisher": {"@type": "Organization", "name": "Análisis.com",
                      "logo": {"@type": "ImageObject",
                               "url": f"{SITE_URL}/favicon.svg"}},
        "mainEntityOfPage": url, "url": url,
        "speakable": {"@type": "SpeakableSpecification",
                      "cssSelector": [".dek", ".claves"]},
    }
    faq = [q for q in (a.get("faq") or []) if q.get("question") and q.get("answer")]
    if faq:
        faqpage = {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q["question"],
             "acceptedAnswer": {"@type": "Answer", "text": q["answer"]}}
            for q in faq]}
        return {"@context": "https://schema.org", "@graph": [noticia, faqpage]}
    noticia["@context"] = "https://schema.org"
    return noticia


# ==================================================================== BUILD
def build():
    if os.path.isdir(OUT):
        try:
            shutil.rmtree(OUT)
        except (PermissionError, OSError):
            pass
    os.makedirs(OUT, exist_ok=True)

    global TICKER_HTML, SERIES_BY_ID, ENGAGEMENT
    TICKER_HTML = build_ticker()
    # Series de datos (data.json) indexadas por id, para los mini-gráficos (T11).
    if os.path.exists(DATA):
        try:
            with open(DATA, encoding="utf-8") as f:
                SERIES_BY_ID = {s["id"]: s for s in json.load(f).get("series", [])}
        except Exception:  # noqa: BLE001
            SERIES_BY_ID = {}
    # Engagement por artículo (analytics.json de GA4): señal de interés (portada).
    if os.path.exists(ANALYTICS_JSON):
        try:
            with open(ANALYTICS_JSON, encoding="utf-8") as f:
                ENGAGEMENT = json.load(f).get("engagement", {}) or {}
        except Exception:  # noqa: BLE001
            ENGAGEMENT = {}
    # Orden de portada: primero por fecha (frescura) y, dentro del mismo día,
    # por IMPORTANCIA (sección prioritaria + fuentes contrastadas + relevancia
    # regional). Así el líder es la nota más relevante del día, no la primera.
    arts = sorted(ARTICLES, key=lambda x: (x["date"], _importancia(x)), reverse=True)
    write_covers(arts)
    write_audio(arts)
    write_briefing(arts)
    temas = build_temas(arts)

    # ---- assets estáticos ----
    app_js = (APP_JS + TICKER_JS + WEATHER_JS + REACT_JS + ASK_JS
              + I18N_JS.replace("__I18N__", json.dumps(I18N, ensure_ascii=False)))
    write(os.path.join(OUT, "assets", "app.css"), CSS)
    write(os.path.join(OUT, "assets", "app.js"), app_js)
    write(os.path.join(OUT, "favicon.svg"), FAVICON)
    # Versiona la caché del SW con un hash de los assets: cualquier cambio
    # invalida la caché vieja y llega a los visitantes recurrentes.
    global ASSET_VER
    swver = hashlib.md5((CSS + app_js).encode("utf-8")).hexdigest()[:8]
    ASSET_VER = swver  # versiona las URLs de app.css/app.js (busta la caché de Cloudflare)
    write(os.path.join(OUT, "sw.js"), SW_JS.replace("__SWVER__", swver))
    write(os.path.join(OUT, "manifest.webmanifest"), json.dumps({
        "name": "Análisis.com", "short_name": "Análisis", "start_url": "/",
        "display": "standalone", "background_color": "#ffffff",
        "theme_color": "#111417",
        "icons": [{"src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml"}]},
        ensure_ascii=False))
    if os.path.exists(DATA):
        shutil.copy(DATA, os.path.join(OUT, "data.json"))
    # GitHub Pages: dominio propio + desactivar Jekyll
    cname = os.environ.get("CNAME", "www.analisis.com").strip()
    if cname:
        write(os.path.join(OUT, "CNAME"), cname + "\n")
    write(os.path.join(OUT, ".nojekyll"), "")

    # ---- índice de búsqueda ----
    idx = [{"id": a["id"], "title": a["title"], "subtitle": a["subtitle"],
            "section": a["section"], "sectionName": SECTION_BY_SLUG[a["section"]]["name"],
            "date": a["date"], "dateLong": fecha_larga(a["date"]),
            "url": f"articulo/{a['id']}.html",
            "tags": a.get("tags", []),
            "countries": _paises(a),
            "text": " ".join(a["body"])[:1200]} for a in arts]
    write(os.path.join(OUT, "search-index.json"), json.dumps(idx, ensure_ascii=False))

    _home(arts)
    _sections(arts)
    _articles(arts, temas)
    _archivo(arts)
    _temas(temas)
    paises, empresas = build_hubs(arts)
    _hub_pages(paises, "pais", "País")
    _hub_pages(empresas, "empresa", "Empresa")
    _buscar()
    _asistente()
    _datos()
    _correcciones()
    _panel()
    _boletin(arts)
    _seo(arts, temas, paises, empresas)

    print(f"OK — sitio generado en {OUT}")
    print(f"     {len(arts)} artículos · {len(SECTIONS)} secciones · {len(temas)} temas"
          f" · {len(paises)} hubs país · {len(empresas)} hubs empresa")
    print(f"     páginas: portada, secciones, artículos, archivo, buscar, asistente, "
          f"datos, boletín, temas + SEO/PWA")


def _region_score(a):
    """Relevancia regional de una nota: usa region_score si existe; si no (notas
    previas a T2), lo calcula desde título + bajada + cuerpo + tags."""
    if "region_score" in a:
        return a["region_score"]
    return puntaje_regional(
        a.get("title", "") + " " + a.get("subtitle", "") + " "
        + " ".join(a.get("body", [])) + " " + " ".join(a.get("tags", [])))


# Prioridad editorial por sección (T3): pondera qué secciones encabezan.
SECTION_PRIORITY = {
    "economia": 3, "mercados": 3, "mineria": 3, "energia": 2, "banca": 2,
    "internacional": 2, "tecnologia": 2, "agricultura": 1, "retail": 1,
    "startups": 1,
}


def _engagement(a):
    """Interacciones (reacciones + votos) de la nota según GA4; 0 si no hay datos."""
    try:
        return int(ENGAGEMENT.get(a["id"], 0))
    except (TypeError, ValueError):
        return 0


def _importancia(a):
    """Score de importancia (T3): prioridad de sección + nº de fuentes
    contrastadas (tope 4) + relevancia regional + señal de interés (interacción
    de los lectores, con tope). La recencia se aplica como clave primaria en el
    orden, no aquí, para no anteponer notas viejas."""
    fuentes = len(a.get("sources_consulted") or [])
    return (SECTION_PRIORITY.get(a["section"], 1)
            + min(fuentes, 4)
            + _region_score(a)
            + min(_engagement(a), 6))


def _mismo_tema(a, b):
    """Dos notas son casi el mismo tema si comparten >=2 tags o sus titulares
    se parecen mucho (para deduplicar la portada)."""
    ta = {t.lower() for t in a.get("tags", [])}
    tb = {t.lower() for t in b.get("tags", [])}
    if ta and len(ta & tb) >= 2:
        return True
    return SequenceMatcher(None, a.get("title", "").lower(),
                           b.get("title", "").lower()).ratio() >= 0.6


def _dedup(arts):
    """Quita casi-duplicados del MISMO día para la portada, conservando el de
    mayor importancia (ya vienen ordenados)."""
    out = []
    for a in arts:
        if any(a["date"] == b["date"] and _mismo_tema(a, b) for b in out):
            continue
        out.append(a)
    return out


def _claves_hoy(arts):
    """Las 5 notas más importantes del día más reciente (ya vienen ordenadas por
    fecha e importancia). Es el 'resumen del día' con enlaces a las fuentes."""
    if not arts:
        return []
    hoy = arts[0]["date"]
    return [a for a in arts if a["date"] == hoy][:5]


def _digest_intro(fecha):
    """Síntesis del día (opcional) que redacta el pipeline con IA; '' si no aplica."""
    try:
        with open(DIGEST_JSON, encoding="utf-8") as f:
            dg = json.load(f)
        if dg.get("date") == fecha:
            return dg.get("intro", "") or ""
    except Exception:  # noqa: BLE001
        pass
    return ""


def _home(arts):
    arts = _dedup(arts)
    lead, rest = arts[0], arts[1:]
    sec = SECTION_BY_SLUG[lead["section"]]
    h = head(f"{SITE['name']} — {SITE['tagline']}", depth=0)
    # barra "Para ti" (personalización)
    h += ('<div id="parati" style="display:none" class="note">Estás siguiendo secciones: '
          'tu portada prioriza esos temas. Gestiona tus intereses con el botón «Seguir» en cada sección.</div>')
    # Asistente "Pregúntale a Análisis" (T15): barra principal sobre las 5 claves.
    h += ('<section class="ask-hero"><div class="section-head"><h2>Pregúntale a Análisis</h2>'
          '<span class="d">Respuesta elaborada con lo publicado + la web</span></div>'
          + ask_widget("Pregunta cualquier cosa: ¿cómo va el cobre? ¿y las tasas en la región?")
          + '</section>')
    # Resumen del día: "Las 5 claves de hoy" (con enlaces a las notas fuente).
    claves = _claves_hoy(arts)
    if claves:
        intro = _digest_intro(claves[0]["date"])
        h += '<section class="claves-dia">'
        h += (f'<div class="section-head"><h2>Las 5 claves de hoy</h2>'
              f'<span class="d">{fecha_larga(claves[0]["date"])}</span>')
        # Botón/reproductor del resumen: a la derecha, sobre la línea de la cabecera.
        if BRIEFING:
            h += (f'<div class="cd-audio"><audio controls preload="none" '
                  f'src="audio/{BRIEFING}"></audio></div>')
        else:
            h += ('<div class="cd-audio"><button class="cd-listen" '
                  'onclick="leerResumen(this)">▶ Escuchar el resumen del día</button></div>')
        h += '</div>'
        if intro:
            h += f'<p class="cd-intro">{escape(intro)}</p>'
        h += '<ol class="cd-list">'
        for a in claves:
            s = SECTION_BY_SLUG[a["section"]]
            h += (f'<li><a href="articulo/{a["id"]}.html">'
                  f'<span class="kicker">{escape(s["name"])}</span> '
                  f'{escape(a["title"])}</a></li>')
        h += '</ol></section>'
    h += '<section class="lead-grid"><div class="lead-main">'
    h += f'<div class="thumb"><img src="{img_path(lead, "")}" alt="{alt_for(lead)}"></div>'
    h += f'<span class="kicker">{escape(sec["name"])}</span>'
    h += f'<h1><a href="articulo/{lead["id"]}.html">{escape(lead["title"])}</a></h1>'
    h += f'<p class="dek">{escape(lead["subtitle"])}</p>'
    h += f'<div class="meta">{fecha_larga(lead["date"])} · {reading_time(lead)} min de lectura</div>'
    h += ('</div><aside class="whatsnews">'
          '<div class="wx" id="wx"><div class="wx-cond" style="padding:6px 0">Cargando el tiempo…</div></div>'
          '<h4>Lo último</h4><div class="wn-list">')
    for a in rest:
        s2 = SECTION_BY_SLUG[a["section"]]
        h += (f'<div class="wn-item"><span class="kicker">{escape(s2["name"])}</span>'
              f'<div class="t"><a href="articulo/{a["id"]}.html">{escape(a["title"])}</a></div></div>')
    h += '</div></aside></section>'
    if ADS:
        h += '<div class="ad">Espacio publicitario</div>'
    paises_ui = [("cl", "Chile"), ("ar", "Argentina"), ("br", "Brasil"),
                 ("mx", "México"), ("co", "Colombia"), ("pe", "Perú"),
                 ("uy", "Uruguay"), ("ec", "Ecuador"), ("bo", "Bolivia"),
                 ("py", "Paraguay"), ("ve", "Venezuela")]
    opciones = '<option value="">Todos los países</option>' + "".join(
        f'<option value="{c}">{escape(n)}</option>' for c, n in paises_ui)
    h += ('<div class="section-head"><h2>Más noticias</h2>'
          '<span class="d">Prioriza tu país y las secciones que sigas</span>'
          f'<label class="paispick">Tu país: <select id="paisSel">{opciones}</select>'
          '<span id="paisAuto" class="d"></span></label></div>')
    h += '<div class="grid" id="masgrid">'
    for a in rest:
        h += card(a, depth=0)
    for p in PLACEHOLDERS:
        h += card(p, depth=0, placeholder=True)
    h += '</div>'
    h += foot(0)
    write(os.path.join(OUT, "index.html"), h)


def _sections(arts):
    for s in SECTIONS:
        arts_s = [a for a in arts if a["section"] == s["slug"]]
        ph_s = [p for p in PLACEHOLDERS if p["section"] == s["slug"]]
        h = head(f"{s['name']} — {SITE['name']}", active=s["slug"], depth=1,
                 description=s["desc"])
        h += (f'<div class="section-head"><h2>{escape(s["name"])}</h2>'
              f'<span class="d">{escape(s["desc"])}</span>'
              f'<button class="chip" data-follow="{s["slug"]}" '
              f'onclick="seguir(\'{s["slug"]}\',this)">Seguir</button></div>')
        h += '<div class="grid">'
        for a in arts_s:
            h += card(a, depth=1)
        for p in ph_s:
            h += card(p, depth=1, placeholder=True)
        if not arts_s and not ph_s:
            h += '<p class="meta">Aún no hay publicaciones en esta sección.</p>'
        h += '</div>'
        h += foot(1)
        write(os.path.join(OUT, "seccion", f"{s['slug']}.html"), h)


def _articles(arts, temas):
    for i, a in enumerate(arts):
        sec = SECTION_BY_SLUG[a["section"]]
        h = head(f"{a['title']} — {SITE['name']}", active="_article", depth=1,
                 description=a["subtitle"], image=f"{SITE_URL}/img/{COVER[a['id']]}",
                 ld=article_ld(a))
        h += '<article class="post">'
        h += f'<span class="kicker">{escape(sec["name"])}</span>'
        h += f'<h1>{escape(a["title"])}</h1>'
        h += f'<p class="dek">{escape(a["subtitle"])}</p>'
        n_fuentes = len(a.get("sources_consulted") or [])
        sello_f = f' · <strong>{n_fuentes} fuentes contrastadas</strong>' if n_fuentes else ''
        h += ('<div class="byline"><span>Por ' + escape(a["author"]) + ' · '
              + fecha_larga(a["date"]) + ' · ' + str(reading_time(a)) + ' min'
              + sello_f + '</span>'
              '<span class="acts">'
              '<button onclick="leer(this)">▶ Escuchar</button>'
              '<button onclick="compartir()">Compartir</button></span></div>')
        # Franja de confianza (T4): actualización con hora + política de correcciones.
        h += (f'<div class="trust">Actualizado: {fecha_hora(a)}'
              + (f' · {n_fuentes} fuentes contrastadas' if n_fuentes else '')
              + ' · <a href="../correcciones.html">Política de correcciones</a></div>')
        if AUDIO.get(a["id"]):
            h += (f'<audio class="tts" preload="none" '
                  f'src="../audio/{AUDIO[a["id"]]}"></audio>')
        credito = a.get("image_credit") or CREDIT.get(a["id"]) or "Portada · Análisis.com"
        h += (f'<figure class="hero"><div class="thumb">'
              f'<img src="../img/{COVER[a["id"]]}" alt="{alt_for(a)}"></div>'
              f'<figcaption>{escape(credito)}</figcaption></figure>')
        if a.get("key_points"):
            h += '<div class="claves"><h4>Claves en 30 segundos</h4><ul>'
            for k in a["key_points"]:
                h += f'<li>{escape(k)}</li>'
            h += '</ul></div>'
        h += '<div id="cuerpo">'
        for p in a["body"]:
            h += f'<p>{escape(p)}</p>'
        h += '</div>'
        # Mini-gráfico del indicador relacionado con la sección (T11).
        serie = _serie_seccion(a["section"])
        if serie:
            h += (f'<div class="art-chart dcard"><div class="kicker">Indicador · '
                  f'{escape(serie["name"])} <span class="meta">({escape(serie["unit"])})</span>'
                  f'</div><canvas id="artchart"></canvas></div>'
                  f'<script>window.__SERIE__={json.dumps(serie, ensure_ascii=False)}</script>'
                  f'<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>'
                  f'<script>{ART_CHART_JS}</script>')
        # Preguntas frecuentes (T12): resumen citable + datos estructurados FAQPage.
        faq = [q for q in (a.get("faq") or []) if q.get("question") and q.get("answer")]
        if faq:
            h += '<div class="faq"><h4>Preguntas frecuentes</h4>'
            for qa in faq:
                h += (f'<details><summary>{escape(qa["question"])}</summary>'
                      f'<p>{escape(qa["answer"])}</p></details>')
            h += '</div>'
        if a.get("tags"):
            h += '<div style="margin-top:22px">' + "".join(
                f'<a class="tag" href="../tema/{slugify(t)}.html">{escape(t)}</a>'
                for t in a["tags"]) + '</div>'
        # Hubs (T9): chips de país y empresa que enlazan a su línea de tiempo.
        hubs = [(f'../pais/{slugify(PAIS_NOMBRE.get(c, c))}.html', PAIS_NOMBRE.get(c, c))
                for c in _paises(a)]
        hubs += [(f'../empresa/{s}.html', EMPRESAS[s]["name"]) for s in _empresas(a)]
        if hubs:
            h += '<div style="margin-top:8px">' + "".join(
                f'<a class="tag" href="{href}">🧭 {escape(nombre)}</a>'
                for href, nombre in hubs) + '</div>'
        if a.get("sources_consulted"):
            fuentes = ", ".join(escape(s) for s in a["sources_consulted"])
            h += (f'<div class="note">Artículo original de Análisis.com, redactado a partir del '
                  f'contraste de información publicada por múltiples medios. Fuentes consultadas: '
                  f'{fuentes}. No reproduce texto de terceros.</div>')
        # Reacciones + encuesta (interacción y señal de interés). Estado en
        # localStorage; los clics disparan eventos GA4 (agregado para la portada).
        h += (f'<div class="react" data-aid="{a["id"]}">'
              '<span class="react-q">¿Qué te pareció?</span>'
              '<button data-r="interesante">👍 Interesante</button>'
              '<button data-r="importante">🔥 Importante</button>'
              '<button data-r="pensar">🤔 Me hace pensar</button>'
              '<button data-r="sorprende">😮 Sorprendente</button></div>')
        poll = a.get("poll") or {}
        opciones = poll.get("options") or []
        if poll.get("question") and len(opciones) >= 2:
            h += (f'<div class="poll" data-aid="{a["id"]}">'
                  f'<h4>Encuesta</h4><p class="poll-q">{escape(poll["question"])}</p>'
                  '<div class="poll-opts">')
            for i, opt in enumerate(opciones[:4]):
                h += f'<button data-i="{i}">{escape(opt)}</button>'
            h += '</div><p class="poll-thanks" hidden>¡Gracias por tu voto!</p></div>'
        # relacionados
        rel = [b for b in arts if b["id"] != a["id"]
               and set(b.get("tags", [])) & set(a.get("tags", []))][:3]
        if not rel:
            rel = [b for b in arts if b["id"] != a["id"] and b["section"] == a["section"]][:3]
        if rel:
            h += '<div class="related"><div class="section-head"><h2>Relacionadas</h2></div><div class="grid">'
            for b in rel:
                h += card(b, depth=1)
            h += '</div></div>'
        h += '</article>'
        h += foot(1)
        write(os.path.join(OUT, "articulo", f"{a['id']}.html"), h)


def _archivo(arts):
    h = head(f"Archivo — {SITE['name']}", depth=0,
             description="Todas las publicaciones anteriores de Análisis.com")
    h += ('<div class="section-head"><h2>Archivo histórico</h2>'
          '<span class="d">Todas las publicaciones anteriores</span></div>')
    by_date = {}
    for a in arts:
        by_date.setdefault(a["date"], []).append(a)
    for date in sorted(by_date, reverse=True):
        h += f'<div class="arch-day">{fecha_larga(date)}</div><div class="grid">'
        for a in by_date[date]:
            h += card(a, depth=0)
        h += '</div>'
    h += foot(0)
    write(os.path.join(OUT, "archivo.html"), h)


def _temas(temas):
    for slug, t in temas.items():
        arts_t = sorted(t["arts"], key=lambda x: x["date"], reverse=True)
        h = head(f"{t['name']} — Tema — {SITE['name']}", depth=1,
                 description=f"Cobertura de Análisis.com sobre {t['name']}")
        h += (f'<div class="section-head"><h2>Tema: {escape(t["name"])}</h2>'
              f'<span class="d">Cobertura y línea de tiempo</span></div>')
        h += '<div class="tl">'
        for a in arts_t:
            sec = SECTION_BY_SLUG[a["section"]]
            h += (f'<div class="it"><span class="kicker">{escape(sec["name"])} · '
                  f'{fecha_larga(a["date"])}</span>'
                  f'<div class="wn-item" style="border:0;padding-top:2px">'
                  f'<div class="t"><a href="../articulo/{a["id"]}.html">{escape(a["title"])}</a></div>'
                  f'<p class="dek">{escape(a["subtitle"])}</p></div></div>')
        h += '</div>'
        h += foot(1)
        write(os.path.join(OUT, "tema", f"{slug}.html"), h)


def _buscar():
    h = head(f"Buscar — {SITE['name']}", depth=0,
             description="Busca en todo el archivo de Análisis.com")
    h += '<div class="section-head"><h2>Buscar</h2><span class="d">Todo el archivo</span></div>'
    h += ('<input id="q" class="searchbox" placeholder="Busca por tema, empresa, país, commodity…" autofocus>'
          '<div id="res" style="margin-top:18px"></div>')
    h += foot(0, extra_js=SEARCH_JS)
    write(os.path.join(OUT, "buscar.html"), h)


def ask_widget(placeholder, autofocus=False, compact=False):
    """Barra del asistente 'Pregúntale a Análisis' (T15). El JS (ASK_JS, en el
    bundle) la cablea: usa el endpoint /ask si ANALISIS_ASK_URL está definido, o
    el modo interno (extractivo sobre search-index) si no."""
    chips = ["¿Cómo va el precio del cobre?",
             "¿Qué pasa con las tasas en la región?",
             "¿Últimas noticias del litio?"]
    af = " autofocus" if autofocus else ""
    cls = "ask ask-compact" if compact else "ask"
    return (f'<div class="{cls}">'
            '<div class="ask-row">'
            f'<input class="ask-q" placeholder="{escape(placeholder)}"{af}>'
            '<button class="ask-go">Preguntar</button></div>'
            '<div class="ask-chips">'
            + "".join(f'<button class="ask-chip">{escape(c)}</button>' for c in chips)
            + '</div><div class="ask-out"></div></div>')


def _asistente():
    h = head(f"Pregúntale a Análisis — {SITE['name']}", depth=0,
             description="Asistente que responde con información de Análisis.com y la web")
    h += ('<div class="section-head"><h2>Pregúntale a Análisis</h2>'
          '<span class="d">Respuesta elaborada con lo publicado + la web</span></div>')
    h += ask_widget("Ej.: ¿Cómo va el precio del cobre? ¿Qué pasa con las tasas?",
                    autofocus=True)
    h += foot(0)
    write(os.path.join(OUT, "asistente.html"), h)


def _correcciones():
    dominio = SITE.get("domain", "analisis.com")
    h = head(f"Política de correcciones — {SITE['name']}", depth=0,
             description="Cómo Análisis.com verifica, actualiza y corrige sus publicaciones.")
    h += ('<div class="section-head"><h2>Política de correcciones</h2>'
          '<span class="d">Transparencia editorial</span></div>')
    h += '<article class="post">'
    h += ('<p>En Análisis.com publicamos <strong>artículos originales</strong> redactados a '
          'partir del contraste de información de <strong>varias fuentes</strong> '
          'internacionales y regionales. Cada nota indica su <strong>fecha y hora de '
          'actualización</strong> y el <strong>número de fuentes contrastadas</strong>.</p>')
    h += ('<p>La exactitud es una prioridad. Si detectas un error de hecho —un dato, una cifra, '
          'un nombre o una fecha— queremos corregirlo cuanto antes.</p>')
    h += (f'<p><strong>Cómo reportar un error:</strong> escríbenos a '
          f'<a href="mailto:correcciones@{dominio}">correcciones@{dominio}</a> indicando el '
          'título de la nota, el dato en cuestión y, si es posible, la fuente correcta.</p>')
    h += ('<p><strong>Cómo corregimos:</strong> verificamos el reporte contra las fuentes; si '
          'procede, actualizamos la nota, dejamos constancia de la corrección y renovamos la '
          'marca de actualización. Las correcciones de fondo se señalan al pie del artículo.</p>')
    h += ('<p>Las notas se generan y actualizan de forma automatizada cada 24 horas; esta '
          'política aplica por igual a todo el contenido publicado.</p>')
    h += '</article>'
    h += foot(0)
    write(os.path.join(OUT, "correcciones.html"), h)


def _datos():
    h = head(f"Datos regionales — {SITE['name']}", depth=0,
             description="Tablero de indicadores regionales: commodities, monedas y tasas")
    h += ('<div class="section-head"><h2>Datos regionales</h2>'
          '<span class="d" id="dupd">Cargando…</span></div>')
    h += ('<p class="meta">Indicadores clave para América Latina. Actualizables '
          'automáticamente con <code>generator/fetch_data.py</code>.</p>')
    # Herramientas interactivas (T11): conversor de divisas + calculadora de commodities.
    h += ('<div class="section-head"><h2>Herramientas</h2></div>'
          '<div class="dgrid" style="margin:14px 0 8px">'
          '<div class="dcard tool"><div class="kicker">Conversor de divisas</div>'
          '<div class="toolrow"><input id="cv-amt" type="number" value="100" min="0" step="any">'
          '<select id="cv-from"></select><span>→</span><select id="cv-to"></select></div>'
          '<div class="toolout" id="cv-out">—</div>'
          '<div class="meta" id="cv-src">Tipo de cambio en vivo</div></div>'
          '<div class="dcard tool"><div class="kicker">Calculadora de commodities</div>'
          '<div class="toolrow"><input id="cc-qty" type="number" value="1" min="0" step="any">'
          '<select id="cc-serie"></select></div>'
          '<div class="toolout" id="cc-out">—</div>'
          '<div class="meta">Con el último valor del tablero</div></div>'
          '</div>')
    h += '<div id="charts" class="dgrid" style="margin:18px 0"></div>'
    h += ('<div class="section-head"><h2>Tasas de política monetaria</h2></div>'
          '<div class="dcard"><table class="rates" id="rates"></table></div>')
    # datos incrustados: funciona incluso abriendo el archivo local (sin servidor)
    if os.path.exists(DATA):
        with open(DATA, encoding="utf-8") as f:
            h += f'<script>window.__DATA__={f.read()}</script>'
    h += '<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>'
    h += foot(0, extra_js=DATOS_JS)
    write(os.path.join(OUT, "datos.html"), h)


PANEL_HTML = """
<style>
.pgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}
.kpi{border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi .v{font-size:30px;font-weight:800;font-family:var(--sans);color:var(--ink)}
.kpi .l{font-family:var(--sans);font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.bar-row{display:grid;grid-template-columns:150px 1fr 130px;gap:10px;align-items:center;padding:5px 0;font-family:var(--sans);font-size:13px}
.bar-row .bl{color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-row .bt{background:var(--wash);border-radius:6px;height:12px;overflow:hidden}
.bar-row .bt i{display:block;height:100%;background:var(--brand-2)}
.bar-row .bt i.alt{background:var(--brand-3)}
.bar-row .bv{color:var(--muted);text-align:right}
.pbox{border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.pbox h3{font-family:var(--sans);font-size:13px;text-transform:uppercase;letter-spacing:.6px;margin:0 0 10px}
#focos ul{margin:0;padding-left:18px}
#focos li{font-family:var(--sans);font-size:14px;margin:6px 0;line-height:1.45;color:var(--ink)}
@media(max-width:700px){.pgrid{grid-template-columns:repeat(2,1fr)!important}.bar-row{grid-template-columns:110px 1fr 88px}}
</style>
<div id="gate" style="max-width:420px;margin:50px auto;text-align:center">
  <div class="section-head" style="justify-content:center;border-color:var(--ink)"><h2>Panel privado</h2></div>
  <p class="meta">Ingresa la clave para ver las estadísticas de visitas.</p>
  <input id="pw" type="password" autocomplete="off" placeholder="Clave"
    style="font-size:16px;padding:10px 12px;width:100%;border:1px solid var(--line2);border-radius:8px;margin:6px 0;background:var(--bg);color:var(--ink)">
  <button onclick="entrar()" style="padding:10px 20px;border:1px solid var(--ink);border-radius:8px;cursor:pointer;font-family:var(--sans);background:var(--bg);color:var(--ink)">Entrar</button>
  <p id="err" class="meta" style="color:var(--red);display:none">Clave incorrecta.</p>
</div>
<div id="panel" style="display:none">
  <div class="section-head"><h2>Visitas del sitio</h2><span class="d" id="rango"></span>
    <button onclick="salir()" class="tb" style="margin-left:auto;border:1px solid var(--line);border-radius:6px;padding:3px 10px;cursor:pointer;background:var(--bg);color:var(--muted)">Salir</button></div>
  <div id="nodata" style="display:none"><p class="meta">Aún no hay datos. Conecta GA4 (secrets <code>GA4_PROPERTY_ID</code> + <code>GA4_CREDENTIALS</code>) y espera a la próxima actualización diaria.</p></div>
  <div class="pgrid">
    <div class="kpi"><div class="v" id="k-ses">–</div><div class="l">Sesiones</div></div>
    <div class="kpi"><div class="v" id="k-usr">–</div><div class="l">Usuarios únicos</div></div>
    <div class="kpi"><div class="v" id="k-vis">–</div><div class="l">Vistas de página</div></div>
    <div class="kpi"><div class="v" id="k-ret">–</div><div class="l">% recurrentes</div></div>
  </div>
  <div class="pbox"><h3>Interés por sección</h3><div id="secs"></div></div>
  <div class="pbox"><h3>Focos sugeridos (inteligencia)</h3><div id="focos"></div></div>
  <div class="pgrid" style="grid-template-columns:1fr 1fr">
    <div class="pbox"><h3>Origen por país</h3><div id="countries"></div></div>
    <div class="pbox"><h3>Nuevos vs recurrentes</h3><div id="nvr"></div></div>
  </div>
</div>
"""

PANEL_JS = r"""
(function(){
  var d=document;
  function n(x){return (x||0).toLocaleString('es-CL');}
  function pct(x){return Math.round((x||0)*100)+'%';}
  function set(id,v){var e=d.getElementById(id); if(e)e.textContent=v;}
  window.salir=function(){try{sessionStorage.removeItem('panel_ok');}catch(e){} location.reload();};
  window.entrar=async function(){
    var pw=(d.getElementById('pw').value||'');
    var buf=await crypto.subtle.digest('SHA-256', new TextEncoder().encode(pw));
    var hex=Array.from(new Uint8Array(buf)).map(function(b){return b.toString(16).padStart(2,'0');}).join('');
    if(hex===window.__PANEL_HASH__){ try{sessionStorage.setItem('panel_ok','1');}catch(e){} mostrar(); }
    else { d.getElementById('err').style.display='block'; }
  };
  function mostrar(){ d.getElementById('gate').style.display='none'; d.getElementById('panel').style.display='block'; render(window.__ANALYTICS__); }
  function barras(host, filas, campo, alt){
    var max=Math.max.apply(null, filas.map(function(f){return f[campo];}).concat([1]));
    d.getElementById(host).innerHTML = filas.length ? filas.map(function(f){
      return '<div class="bar-row"><span class="bl">'+f.label+'</span>'+
        '<span class="bt"><i class="'+(alt||'')+'" style="width:'+Math.round(100*f[campo]/max)+'%"></i></span>'+
        '<span class="bv">'+f.right+'</span></div>';
    }).join('') : '<p class="meta">Sin datos.</p>';
  }
  function render(a){
    if(!a){ d.getElementById('nodata').style.display='block'; return; }
    var r=a.new_vs_returning||{new:0,returning:0};
    var totU=(r.new+r.returning)||a.totals.users||0;
    var pRet=totU? r.returning/totU : 0;
    set('k-ses',n(a.totals.sessions)); set('k-usr',n(a.totals.users));
    set('k-vis',n(a.totals.pageviews)); set('k-ret',pct(pRet));
    set('rango','Últimos '+a.range_days+' días · actualizado '+a.updated);
    var secs=(a.sections||[]);
    barras('secs', secs.map(function(s){return {label:s.name, pageviews:s.pageviews, right:n(s.pageviews)+' · '+pct(s.share)};}), 'pageviews');
    barras('countries', (a.countries||[]).map(function(c){return {label:c.country, sessions:c.sessions, right:n(c.sessions)};}), 'sessions');
    barras('nvr', [
      {label:'Nuevos', v:r.new, right:n(r.new)},
      {label:'Recurrentes', v:r.returning, right:n(r.returning)}
    ], 'v');
    // colorear la barra de recurrentes distinto
    var nvr=d.getElementById('nvr'); if(nvr && nvr.querySelectorAll('i')[1]) nvr.querySelectorAll('i')[1].classList.add('alt');
    d.getElementById('focos').innerHTML=insight(secs.filter(function(s){return s.section!=='portada'&&s.section!=='otras';}), pRet);
  }
  function insight(secs, pRet){
    if(!secs.length) return '<p class="meta">Cuando haya tráfico por sección, aquí verás recomendaciones de foco.</p>';
    var top=secs.slice(0,2).map(function(s){return s.name;});
    var bottom=secs.slice(-2).map(function(s){return s.name;});
    var shareTop=secs.slice(0,3).reduce(function(x,s){return x+s.share;},0);
    var out='<ul>';
    out+='<li><strong>Mayor interés:</strong> '+top.join(' y ')+'. Concentran el grueso del tráfico; conviene <b>reforzar cobertura y frecuencia</b> ahí.</li>';
    out+='<li>Las 3 secciones más leídas suman el <strong>'+pct(shareTop)+'</strong> del tráfico por sección.</li>';
    if(secs.length>3) out+='<li><strong>Menor tracción:</strong> '+bottom.join(' y ')+'. Evalúa mejorar titulares/portadas o reenfocar el esfuerzo.</li>';
    out+='<li><strong>'+pct(pRet)+'</strong> de los visitantes son <b>recurrentes</b>'+(pRet>=0.3?' — buena fidelización; potencia boletín y alertas.':' — hay margen para fidelizar (boletín, "Para ti", WhatsApp).')+'</li>';
    return out+'</ul>';
  }
  try{ if(sessionStorage.getItem('panel_ok')==='1'){ mostrar(); } }catch(e){}
  var pw=d.getElementById('pw'); if(pw) pw.addEventListener('keydown',function(e){ if(e.key==='Enter') entrar(); });
})();
"""


def _panel():
    h = head(f"Panel privado — {SITE['name']}", depth=0,
             description="Panel privado de estadísticas de visitas")
    # excluir de buscadores
    h = h.replace('<meta name="theme-color"',
                  '<meta name="robots" content="noindex,nofollow">'
                  '<meta name="theme-color"')
    phash = hashlib.sha256(PANEL_PASSWORD.encode("utf-8")).hexdigest()
    datos = "null"
    if os.path.exists(ANALYTICS_JSON):
        with open(ANALYTICS_JSON, encoding="utf-8") as f:
            datos = f.read()
    h += PANEL_HTML
    h += f'<script>window.__PANEL_HASH__="{phash}";window.__ANALYTICS__={datos};</script>'
    h += foot(0, extra_js=PANEL_JS)
    write(os.path.join(OUT, "panel.html"), h)


def _boletin(arts):
    by_date = {}
    for a in arts:
        by_date.setdefault(a["date"], []).append(a)
    dates = sorted(by_date, reverse=True)
    # índice
    h = head(f"Boletín — {SITE['name']}", depth=1, description="Boletín diario de Análisis.com")
    h += ('<div class="section-head"><h2>Boletín diario</h2>'
          '<span class="d">Recibe lo esencial cada mañana</span></div>')
    h += ('<p>Suscríbete para recibir el boletín por email. '
          '<em>(Conecta tu proveedor de email en <code>generator/distribute.py</code>.)</em></p>'
          '<form onsubmit="alert(\'Gracias. Conecta el proveedor de email para activar el alta.\');return false" '
          'style="margin:14px 0"><input class="searchbox" placeholder="tu@email.com" '
          'style="max-width:340px;display:inline-block"> <button class="chip on">Suscribirme</button></form>')
    for date in dates:
        h += f'<div class="arch-day">{fecha_larga(date)}</div><ul>'
        for a in by_date[date]:
            h += f'<li style="margin:6px 0"><a href="{slugify(date)}.html">Edición</a> — {escape(a["title"])}</li>'
        h += '</ul>'
        break  # solo enlazamos la última edición como ejemplo
    h += foot(1)
    write(os.path.join(OUT, "boletin", "index.html"), h)
    # edición diaria
    for date in dates:
        day = by_date[date]
        h = head(f"Boletín {fecha_larga(date)} — {SITE['name']}", depth=1)
        h += f'<div class="section-head"><h2>Boletín · {fecha_larga(date)}</h2></div>'
        for a in day:
            sec = SECTION_BY_SLUG[a["section"]]
            h += (f'<div class="wn-item"><span class="kicker">{escape(sec["name"])}</span>'
                  f'<div class="t"><a href="../articulo/{a["id"]}.html">{escape(a["title"])}</a></div>'
                  f'<p class="dek">{escape(a["subtitle"])}</p>')
            if a.get("key_points"):
                h += '<ul>' + "".join(f'<li>{escape(k)}</li>' for k in a["key_points"][:2]) + '</ul>'
            h += '</div>'
        h += foot(1)
        write(os.path.join(OUT, "boletin", f"{slugify(date)}.html"), h)


def _seo(arts, temas, paises=None, empresas=None):
    now = datetime.now().strftime("%Y-%m-%d")
    urls = [f"{SITE_URL}/", f"{SITE_URL}/archivo.html", f"{SITE_URL}/buscar.html",
            f"{SITE_URL}/asistente.html", f"{SITE_URL}/datos.html",
            f"{SITE_URL}/correcciones.html", f"{SITE_URL}/boletin/index.html"]
    urls += [f"{SITE_URL}/seccion/{s['slug']}.html" for s in SECTIONS]
    urls += [f"{SITE_URL}/tema/{slug}.html" for slug in temas]
    urls += [f"{SITE_URL}/pais/{slug}.html" for slug in (paises or {})]
    urls += [f"{SITE_URL}/empresa/{slug}.html" for slug in (empresas or {})]
    urls += [f"{SITE_URL}/articulo/{a['id']}.html" for a in arts]
    sm = ('<?xml version="1.0" encoding="UTF-8"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{u}</loc><lastmod>{now}</lastmod></url>" for u in urls)
          + "</urlset>")
    write(os.path.join(OUT, "sitemap.xml"), sm)

    # news sitemap (últimas 48h aprox: aquí todas las de la última fecha)
    last = arts[0]["date"] if arts else now
    recent = [a for a in arts if a["date"] == last]
    ns = ('<?xml version="1.0" encoding="UTF-8"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
          'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">'
          + "".join(
              f'<url><loc>{SITE_URL}/articulo/{a["id"]}.html</loc>'
              f'<news:news><news:publication><news:name>Análisis.com</news:name>'
              f'<news:language>es</news:language></news:publication>'
              f'<news:publication_date>{a["date"]}</news:publication_date>'
              f'<news:title>{escape(a["title"])}</news:title></news:news></url>'
              for a in recent)
          + "</urlset>")
    write(os.path.join(OUT, "sitemap-news.xml"), ns)

    write(os.path.join(OUT, "robots.txt"),
          f"User-agent: *\nAllow: /\nDisallow: /panel.html\n"
          f"Sitemap: {SITE_URL}/sitemap.xml\n"
          f"Sitemap: {SITE_URL}/sitemap-news.xml\n")

    # RSS general
    items = "".join(
        f"<item><title>{escape(a['title'])}</title>"
        f"<link>{SITE_URL}/articulo/{a['id']}.html</link>"
        f"<guid>{SITE_URL}/articulo/{a['id']}.html</guid>"
        f"<pubDate>{a['date']}</pubDate>"
        f"<description>{escape(a['subtitle'])}</description>"
        f"<category>{escape(SECTION_BY_SLUG[a['section']]['name'])}</category></item>"
        for a in arts)
    rss = ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
           f"<title>Análisis.com</title><link>{SITE_URL}/</link>"
           f"<description>{escape(SITE['tagline'])}</description><language>es</language>"
           + items + "</channel></rss>")
    write(os.path.join(OUT, "rss.xml"), rss)


if __name__ == "__main__":
    with open(CONTENT, encoding="utf-8") as f:
        DATA_JSON = json.load(f)
    SITE = DATA_JSON["site"]
    SECTIONS = DATA_JSON["sections"]
    ARTICLES = DATA_JSON["articles"]
    PLACEHOLDERS = DATA_JSON.get("placeholders", [])
    SECTION_BY_SLUG = {s["slug"]: s for s in SECTIONS}
    build()
