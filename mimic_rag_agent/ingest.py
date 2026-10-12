import os
import pandas as pd
from tqdm import tqdm
from .config import DATA_DIR, SQLITE_PATH
from .utils import sqlite_conn

NEEDED = [
    "ADMISSIONS","PATIENTS","DIAGNOSES_ICD","D_ICD_DIAGNOSES",
    "PRESCRIPTIONS","LABEVENTS","D_LABITEMS","NOTEEVENTS"
]

def run():
    with sqlite_conn(SQLITE_PATH) as conn:
        for t in NEEDED:
            p = os.path.join(DATA_DIR, f"{t}.csv")
            if not os.path.exists(p):
                print(f"[INGEST] {t} 없음 → 건너뜀")
                continue
            print(f"[INGEST] {t} 적재중 ...")
            df = pd.read_csv(p)
            for c in df.columns:
                if df[c].dtype == "object":
                    df[c] = df[c].astype(str).str.strip()
            df.to_sql(t.lower(), conn, if_exists="replace", index=False)

        c = conn.cursor()
        c.execute("CREATE INDEX IF NOT EXISTS idx_adm_hadm ON admissions(hadm_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_diag_hadm ON diagnoses_icd(hadm_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_diag_code ON diagnoses_icd(icd9_code)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_dicd_code ON d_icd_diagnoses(icd9_code)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_presc_hadm ON prescriptions(hadm_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_note_hadm ON noteevents(hadm_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lab_hadm ON labevents(hadm_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_dlab_item ON d_labitems(itemid)")
        print("[INGEST] 완료")
