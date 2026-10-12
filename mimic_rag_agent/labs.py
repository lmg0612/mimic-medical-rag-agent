import json
from collections import defaultdict
from .utils import sqlite_conn, load_json
from .config import SQLITE_PATH
import os

ART = os.path.join(os.path.dirname(os.path.dirname(__file__)), "artifacts")
RANGES = load_json(os.path.join(ART, "lab_ranges.json"), default={})

KEY_MAP = {
    "WBC": ["WBC", "WHITE BLOOD", "WHITE BLOOD CELL"],
    "HGB": ["HGB", "HEMOGLOBIN"],
    "NA": ["NA", "SODIUM"],
    "K": ["K", "POTASSIUM"],
    "CREATININE": ["CREATININE"]
}

def _norm_label(label:str):
    L = (label or "").upper()
    for k, al in KEY_MAP.items():
        for a in al:
            if a in L:
                return k
    return None

def per_hadm_latest(hadm_id:int):
    # hadm의 마지막 측정값들 요약
    rows = []
    with sqlite_conn(SQLITE_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT le.hadm_id, dl.label, le.valuenum, le.valueuom, le.charttime
            FROM labevents le
            LEFT JOIN d_labitems dl ON le.itemid = dl.itemid
            WHERE le.hadm_id = ? AND le.valuenum IS NOT NULL
            ORDER BY le.charttime ASC
        """, (hadm_id,))
        rows = c.fetchall()
    latest = {}
    for _, label, val, uom, t in rows:
        key = _norm_label(label)
        if not key: continue
        latest[key] = (val, uom, t)
    # 해석
    out = []
    for k, (v, u, t) in latest.items():
        rng = RANGES.get(k, {})
        low, high = rng.get("low"), rng.get("high")
        state = "정상 범위"
        if low is not None and v < low: state = "낮음"
        if high is not None and v > high: state = "높음"
        out.append({
            "code": k, "value": v, "unit": u, "time": t,
            "range": {"low": low, "high": high},
            "assessment": state, "desc_kor": rng.get("desc_kor","")
        })
    return out
