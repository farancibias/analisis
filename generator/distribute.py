#!/usr/bin/env python3
"""
Distribución de titulares a canales directos.
============================================
Publica los titulares del día en Telegram y (opcional) WhatsApp, y prepara el
envío del boletín por email. Cada canal se activa solo si defines sus secrets;
si no, se omite sin romper nada.

Secrets (variables de entorno):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   -> canal de Telegram (fácil, gratis)
  WHATSAPP_TOKEN, WHATSAPP_PHONE_ID      -> WhatsApp Cloud API (Meta)
  EMAIL_API_KEY                          -> proveedor de email (boletín)

Uso:  python3 generator/distribute.py
"""

import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content", "articles.json")
SITE_URL = os.environ.get("SITE_URL", "https://analisis.com")


def titulares_de_hoy():
    with open(CONTENT, encoding="utf-8") as f:
        arts = json.load(f)["articles"]
    hoy = datetime.utcnow().strftime("%Y-%m-%d")
    dia = [a for a in arts if a["date"] == hoy] or sorted(
        arts, key=lambda x: x["date"], reverse=True)[:5]
    return dia


def _mensaje(arts):
    lineas = ["*Análisis.com — lo más importante de hoy*", ""]
    for a in arts:
        lineas.append(f"• {a['title']}\n{SITE_URL}/articulo/{a['id']}.html")
    return "\n".join(lineas)


def telegram(arts):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("  Telegram: sin credenciales, omitido.")
        return
    import requests
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": _mensaje(arts),
              "parse_mode": "Markdown", "disable_web_page_preview": False},
        timeout=20)
    print("  Telegram:", "enviado" if r.ok else f"error {r.status_code}")


def whatsapp(arts):
    token = os.environ.get("WHATSAPP_TOKEN")
    phone = os.environ.get("WHATSAPP_PHONE_ID")
    if not (token and phone):
        print("  WhatsApp: sin credenciales, omitido.")
        return
    # WhatsApp Cloud API requiere plantillas aprobadas para difusión.
    # Aquí va la llamada a https://graph.facebook.com/v20.0/{phone}/messages
    print("  WhatsApp: configura tu plantilla aprobada en distribute.py.")


def email_boletin():
    if not os.environ.get("EMAIL_API_KEY"):
        print("  Email: sin proveedor configurado, omitido.")
        return
    # Envía site/boletin/<hoy>.html con tu proveedor transaccional.
    print("  Email: conecta aquí tu proveedor (envío del boletín).")


if __name__ == "__main__":
    arts = titulares_de_hoy()
    print(f"Distribuyendo {len(arts)} titulares...")
    telegram(arts)
    whatsapp(arts)
    email_boletin()
