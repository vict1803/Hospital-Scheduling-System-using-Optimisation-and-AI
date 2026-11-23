"""
SHARED SETTINGS + HELPERS for the black-box tests (no application code is imported).
EDIT THE SETTINGS BLOCK FIRST: urls, CSV column names, data-testid selectors are placeholders.
Run from this folder:  APP_URL=http://localhost:8000 APP_ADMIN_USER=.. APP_ADMIN_PASS=.. APP_STAFF_USER=.. APP_STAFF_PASS=.. pytest -v
"""
import csv
import json
import os
import re
from datetime import datetime, timedelta

import pytest

# =====================================================================================
# SETTINGS  (edit these to match your app)
# =====================================================================================
BASE_URL = os.getenv("APP_URL", "http://localhost:8000")
ADMIN = (os.getenv("APP_ADMIN_USER", "admin"), os.getenv("APP_ADMIN_PASS", "admin"))
STAFF = (os.getenv("APP_STAFF_USER", "staff"), os.getenv("APP_STAFF_PASS", "staff"))

URL = {"login": "/login/", "upload": "/forecast/upload/", "forecast": "/forecast/",
       "staffing": "/forecast/staffing/", "dashboard": "/analytics/", "trends": "/analytics/trends/"}

ED_COLS = ("timestamp", "arrivals")      # CSV header names the upload expects
ICU_COLS = ("date", "census")
HOURLY, DAILY = "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"
MIN_ED_HOURS = 24 * 28                   # TBC: minimum ED history the system needs (ask developer)
MIN_COVER_ED = MIN_COVER_ICU = 1         # TBC: minimum doctors when demand is 0 (not in the report)

S = {  # data-testid placeholders
    "user": "[data-testid=login-username]", "pass": "[data-testid=login-password]", "login": "[data-testid=login-submit]",
    "dtype": "[data-testid=dataset-type]", "file": "[data-testid=upload-file]", "up_btn": "[data-testid=upload-submit]",
    "up_ok": "[data-testid=upload-success]", "up_err": "[data-testid=upload-error]",
    "up_warn": "[data-testid=upload-warning]", "rows": "[data-testid=rows-loaded]",
    "f_ward": "[data-testid=forecast-ward]", "f_go": "[data-testid=generate-forecast]",
    "f_row": "[data-testid=forecast-row]",            # attributes: data-ts, data-value
    "mae_m": "[data-testid=mae-model]", "mae_b": "[data-testid=mae-baseline]",
    "better": "[data-testid=model-beats-baseline]",   # attribute data-better="true|false"
    "f_err": "[data-testid=forecast-error]",
    "s_ward": "[data-testid=staffing-ward]", "s_in": "[data-testid=staffing-forecast-input]",
    "s_go": "[data-testid=staffing-calculate]", "s_out": "[data-testid=staffing-doctors]",
    "s_err": "[data-testid=staffing-error]",
    "s_row": "[data-testid=staffing-row]",             # attributes: data-shift, data-forecast, data-doctors
    "d_ward": "[data-testid=filter-ward]", "d_from": "[data-testid=filter-from]", "d_to": "[data-testid=filter-to]",
    "d_apply": "[data-testid=filter-apply]", "d_chart": "[data-testid=demand-chart]",  # data-points='[["2026-01-05",24],..]'
    "d_empty": "[data-testid=empty-data-message]", "d_err": "[data-testid=filter-error]",
    "t_group": "[data-testid=trend-group-by]", "t_hol": "[data-testid=trend-holiday]",
    "t_hol_na": "[data-testid=holiday-unavailable]", "t_err": "[data-testid=chart-error]",
}

# =====================================================================================
# Tiny in-file helpers (browser steps + CSV writing). No application code is used.
# =====================================================================================
START = datetime(2026, 1, 5)             # a Monday


def visible(page, sel, ms=3000):
    try:
        page.locator(sel).first.wait_for(state="visible", timeout=ms)
        return True
    except Exception:
        return False


def text(page, sel):
    return page.locator(sel).first.inner_text().strip()


def login(page, creds):
    page.goto(BASE_URL + URL["login"])
    page.fill(S["user"], creds[0]); page.fill(S["pass"], creds[1]); page.click(S["login"])
    page.wait_for_load_state("networkidle")


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    return path


def hourly(values, start=START):          # [[timestamp, value], ...]
    return [[(start + timedelta(hours=i)).strftime(HOURLY), v] for i, v in enumerate(values)]


def daily(values, start=START):
    return [[(start + timedelta(days=i)).strftime(DAILY), v] for i, v in enumerate(values)]


def ed_file(tmp, values, name="ed.csv", start=START, header=ED_COLS):
    return write_csv(tmp / name, header, hourly(values, start))


def icu_file(tmp, values, name="icu.csv", start=START, header=ICU_COLS):
    return write_csv(tmp / name, header, daily(values, start))


def weekly_ed(weeks, last_week_extra=0):
    """Hourly arrivals repeating every week (5 + hour of day); optional +extra in the final week."""
    return [5 + (h % 24) + (last_week_extra if h // 168 == weeks - 1 else 0) for h in range(weeks * 168)]


def weekly_icu(weeks, last_week_extra=0):
    return [8 + (d % 7) + (last_week_extra if d // 7 == weeks - 1 else 0) for d in range(weeks * 7)]


def upload(page, ward, path):
    """returns (accepted, message, rows_loaded, warning)"""
    page.goto(BASE_URL + URL["upload"])
    page.select_option(S["dtype"], ward)
    page.set_input_files(S["file"], str(path))
    page.click(S["up_btn"])
    warn = text(page, S["up_warn"]) if visible(page, S["up_warn"], 1500) else ""
    if visible(page, S["up_ok"], 4000):
        n = None
        if visible(page, S["rows"], 500):
            m = re.search(r"\d[\d,]*", text(page, S["rows"])); n = int(m.group().replace(",", "")) if m else None
        return True, text(page, S["up_ok"]), n, warn
    return False, (text(page, S["up_err"]) if visible(page, S["up_err"], 2000) else ""), None, warn


def forecast(page, ward):
    page.goto(BASE_URL + URL["forecast"])
    page.select_option(S["f_ward"], ward); page.click(S["f_go"]); page.wait_for_load_state("networkidle")


def forecast_rows(page):
    r = page.locator(S["f_row"])
    return [(r.nth(i).get_attribute("data-ts"), float(r.nth(i).get_attribute("data-value"))) for i in range(r.count())]


def mae(page):
    num = lambda s: float(re.search(r"-?\d+(\.\d+)?", text(page, s)).group())
    return num(S["mae_m"]), num(S["mae_b"])


def staffing(page, ward, value):
    page.goto(BASE_URL + URL["staffing"])
    page.select_option(S["s_ward"], ward); page.fill(S["s_in"], str(value)); page.click(S["s_go"])
    if visible(page, S["s_err"], 1500):
        return {"error": text(page, S["s_err"])}
    return {"doctors": int(re.search(r"\d+", text(page, S["s_out"])).group())}


def set_filters(page, ward=None, d_from=None, d_to=None, url="dashboard"):
    if page.url.rstrip("/") != (BASE_URL + URL[url]).rstrip("/"):
        page.goto(BASE_URL + URL[url])
    if ward: page.select_option(S["d_ward"], ward)
    if d_from: page.fill(S["d_from"], d_from)
    if d_to: page.fill(S["d_to"], d_to)
    page.click(S["d_apply"]); page.wait_for_load_state("networkidle")


def points(page):
    return [(str(l), float(v)) for l, v in json.loads(page.locator(S["d_chart"]).first.get_attribute("data-points"))]


def shown(page):                          # {"2026-01-05": 24.0, ...}
    return {l[:10]: v for l, v in points(page)}


# ---- datasets for dashboard/trend tests, hand-computable ----------------------------
# ED day d (0-based) has (d+1) arrivals EVERY hour  -> daily total = 24*(d+1).  ICU day d census = d+1.
ED_DAYS, ICU_DAYS = 42, 42
ED_DASH = [(d // 24) + 1 for d in range(ED_DAYS * 24)]
ICU_DASH = [d + 1 for d in range(ICU_DAYS)]
EXPECTED_DAILY = {
    "ED": {str((START + timedelta(days=d)).date()): 24 * (d + 1) for d in range(ED_DAYS)},
    "ICU": {str((START + timedelta(days=d)).date()): d + 1 for d in range(ICU_DAYS)},
}


def between(ward, a, b):
    return {d: v for d, v in EXPECTED_DAILY[ward].items() if a <= d <= b}


