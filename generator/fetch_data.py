#!/usr/bin/env python3
"""
Actualiza content/data.json con datos regionales reales.
=======================================================
Esqueleto funcional: define de dónde traer cada serie. Las funciones traen
valores desde APIs públicas; donde no configuraste una fuente, conserva el
último valor guardado (el tablero nunca queda vacío).

Fuentes sugeridas (gratuitas o freemium):
  - Tipos de cambio: exchangerate.host / open.er-api.com (sin clave)
  - Metales y commodities: metals.dev, metalpriceapi, o feeds de bolsas
  - Tasas de bancos centrales: se editan a mano o vía series del FMI/BIS
  - Indicadores macro: API del Banco Mundial (sin clave)

Uso:  pip install requests ; python3 generator/fetch_data.py
"""

import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "content", "data.json")


def fx_usd(monedas):
    """Tipos de cambio USD->moneda desde una API sin clave. Devuelve dict."""
    import requests
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=20)
        rates = r.json().get("rates", {})
        return {m: rates.get(m) for m in monedas if rates.get(m)}
    except Exception as e:  # noqa: BLE001
        print("  aviso: FX no disponible:", e)
        return {}


def actualizar():
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    mes = datetime.utcnow().strftime("%Y-%m")

    # --- Monedas (ejemplo real, sin clave) ---
    fx = fx_usd({"CLP": "clp", "BRL": "brl", "MXN": "mxn"})
    mapa = {"clp": "CLP", "brl": "BRL", "mxn": "MXN"}
    for s in d["series"]:
        if s["id"] in mapa and mapa[s["id"]] in fx:
            val = round(fx[mapa[s["id"]]], 2)
            if s["points"] and s["points"][-1][0] == mes:
                s["points"][-1][1] = val
            else:
                s["points"].append([mes, val])
            s["points"] = s["points"][-13:]  # conserva ~1 año

    # --- Commodities: aquí conectas tu proveedor de metales/granos ---
    #   for s in d["series"]:
    #       if s["id"] in ("cobre","litio","oro","trigo","soja"):
    #           s["points"].append([mes, traer_precio(s["id"])])
    #   (implementa traer_precio con tu API elegida)

    d["updated"] = datetime.utcnow().strftime("%Y-%m-%d")
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"data.json actualizado ({d['updated']}).")


if __name__ == "__main__":
    actualizar()
