#!/usr/bin/env python3
"""
Analítica del sitio (Google Analytics 4) para el panel privado.
================================================================
Consulta la GA4 Data API con una cuenta de servicio y escribe
content/analytics.json (visitas, únicos vs recurrentes, países y desglose por
sección). El panel (/panel.html) lee esos datos. La clave del servicio vive en
los secrets del workflow, nunca en el navegador.

Se activa con:
  GA4_PROPERTY_ID   id numérico de la propiedad GA4 (p.ej. 123456789)
  GA4_CREDENTIALS   JSON de la cuenta de servicio (con acceso Viewer a la propiedad)
  ANALYTICS_DAYS    (opcional) ventana en días; por defecto 28

Si falta la configuración o la API falla, no escribe nada y el panel muestra
"conecta GA4". Requiere:  pip install google-analytics-data
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content", "articles.json")
OUT = os.path.join(ROOT, "content", "analytics.json")
DIAS = int(os.environ.get("ANALYTICS_DAYS") or "28")


def _mapa_secciones():
    """Devuelve (id_articulo -> slug_sección, slug -> nombre)."""
    id2sec, nombres = {}, {}
    try:
        with open(CONTENT, encoding="utf-8") as f:
            data = json.load(f)
        for s in data.get("sections", []):
            nombres[s["slug"]] = s.get("name", s["slug"])
        for a in data.get("articles", []):
            id2sec[a["id"]] = a["section"]
    except Exception:  # noqa: BLE001
        pass
    return id2sec, nombres


def _seccion_de_ruta(path, id2sec):
    if path in ("/", "/index.html"):
        return "portada"
    if path.startswith("/seccion/"):
        return path.split("/seccion/")[1].split(".html")[0]
    if path.startswith("/articulo/"):
        aid = path.split("/articulo/")[1].split(".html")[0]
        return id2sec.get(aid, "otras")
    return "otras"


def fetch_analytics():
    """Consulta GA4 y devuelve el dict de estadísticas, o None si no aplica."""
    prop = os.environ.get("GA4_PROPERTY_ID")
    cred_json = os.environ.get("GA4_CREDENTIALS")
    if not prop or not cred_json:
        print("analytics: sin GA4_PROPERTY_ID/GA4_CREDENTIALS -> panel sin datos.")
        return None
    try:
        from google.oauth2 import service_account
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            RunReportRequest, DateRange, Dimension, Metric, OrderBy)

        creds = service_account.Credentials.from_service_account_info(
            json.loads(cred_json))
        client = BetaAnalyticsDataClient(credentials=creds)
        prop_name = f"properties/{prop}"
        rng = [DateRange(start_date=f"{DIAS}daysAgo", end_date="today")]

        def run(dimensions=None, metrics=None, order=None, limit=None):
            req = RunReportRequest(
                property=prop_name, date_ranges=rng,
                dimensions=[Dimension(name=d) for d in (dimensions or [])],
                metrics=[Metric(name=m) for m in (metrics or [])],
                order_bys=order or [], limit=limit)
            return client.run_report(req)

        # --- totales ---
        r = run(metrics=["sessions", "totalUsers", "screenPageViews"])
        row = r.rows[0].metric_values if r.rows else None
        totals = {
            "sessions": int(row[0].value) if row else 0,
            "users": int(row[1].value) if row else 0,
            "pageviews": int(row[2].value) if row else 0,
        }

        # --- nuevos vs recurrentes (usuarios) ---
        nvr = {"new": 0, "returning": 0}
        r = run(dimensions=["newVsReturning"], metrics=["totalUsers"])
        for row in r.rows:
            etiqueta = (row.dimension_values[0].value or "").lower()
            n = int(row.metric_values[0].value)
            if etiqueta.startswith("new"):
                nvr["new"] += n
            elif etiqueta.startswith("return"):
                nvr["returning"] += n

        # --- países (top) ---
        orden = [OrderBy(desc=True, metric=OrderBy.MetricOrderBy(metric_name="sessions"))]
        r = run(dimensions=["country"], metrics=["sessions"], order=orden, limit=15)
        countries = [{"country": row.dimension_values[0].value or "—",
                      "sessions": int(row.metric_values[0].value)} for row in r.rows]

        # --- desglose por sección (desde pagePath) ---
        id2sec, nombres = _mapa_secciones()
        r = run(dimensions=["pagePath"], metrics=["screenPageViews"], limit=500)
        por_sec = {}
        for row in r.rows:
            sec = _seccion_de_ruta(row.dimension_values[0].value, id2sec)
            por_sec[sec] = por_sec.get(sec, 0) + int(row.metric_values[0].value)
        total_sec = sum(por_sec.values()) or 1
        sections = sorted(
            ({"section": s, "name": nombres.get(s, s.capitalize()),
              "pageviews": v, "share": round(v / total_sec, 4)}
             for s, v in por_sec.items()),
            key=lambda x: x["pageviews"], reverse=True)

        import datetime
        return {
            "updated": datetime.date.today().isoformat(),
            "range_days": DIAS,
            "totals": totals,
            "new_vs_returning": nvr,
            "countries": countries,
            "sections": sections,
        }
    except Exception as e:  # noqa: BLE001
        print(f"analytics: falló la consulta a GA4 ({e}); panel sin datos.")
        return None


def main():
    stats = fetch_analytics()
    if stats:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"analytics: escrito {OUT} "
              f"({stats['totals']['sessions']} sesiones, "
              f"{len(stats['sections'])} secciones).")


if __name__ == "__main__":
    main()
