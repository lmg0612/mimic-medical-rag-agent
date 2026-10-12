import os, csv
from .utils import sqlite_conn, safe_lower
from .config import SQLITE_PATH

ART = os.path.join(os.path.dirname(os.path.dirname(__file__)), "artifacts")

def load_sym_lex():
    path = os.path.join(ART, "symptom_lex.csv")
    lex = []  # list of (eng, kor, eng_aliases[])
    with open(path, "r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            eng = r["eng"].strip()
            kor = r["kor"].strip()
            aliases = [a.strip() for a in (r.get("eng_aliases","") or "").split("|") if a.strip()]
            lex.append((eng, kor, aliases))
    return lex

def load_neg_cues():
    cues = []
    path = os.path.join(ART, "negation_cues.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                t = line.strip().lower()
                if t:
                    cues.append(t)
    return cues

def contains_negation(sent_l:str, term:str, cues, window=8):
    # simple NegEx-like: if a negation cue appears within a left window before the term
    toks = [t for t in sent_l.split() if t]
    try:
        tidx = toks.index(term.split()[0])  # use first token of term
    except ValueError:
        return False
    left = max(0, tidx-window)
    ctx = " ".join(toks[left:tidx])
    return any(c in ctx for c in cues)

def run():
    lex = load_sym_lex()
    cues = load_neg_cues()

    with sqlite_conn(SQLITE_PATH) as conn:
        c = conn.cursor()

        # conditions
        c.execute("DROP TABLE IF EXISTS kb_conditions")
        c.execute("""
            CREATE TABLE kb_conditions AS
            SELECT d.hadm_id, d.icd9_code, dd.long_title AS cond_name
            FROM diagnoses_icd d
            LEFT JOIN d_icd_diagnoses dd ON d.icd9_code = dd.icd9_code
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_kbc_hadm ON kb_conditions(hadm_id)")

        # treatments (NOTE: no starttime/endtime in MIMIC-III prescriptions)
        c.execute("DROP TABLE IF EXISTS kb_treatments")
        c.execute("""
            CREATE TABLE kb_treatments AS
            SELECT hadm_id, drug,
                   dose_val_rx AS dose_val,
                   dose_unit_rx AS dose_unit,
                   route
            FROM prescriptions
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_kbt_hadm ON kb_treatments(hadm_id)")

        # symptoms (from notes, with negation handling)
        c.execute("DROP TABLE IF EXISTS kb_symptoms")
        c.execute("CREATE TABLE kb_symptoms (hadm_id INTEGER, note_id INTEGER, sentence TEXT, symptom_eng TEXT, symptom_kor TEXT)")

        for (rowid, hadm_id, text) in c.execute("SELECT rowid, hadm_id, text FROM noteevents"):
            if not text:
                continue
            for sent in text.split('\\n'):
                s = (sent or "").strip()
                if not s:
                    continue
                s_l = safe_lower(s)
                for eng, kor, aliases in lex:
                    for can in [eng] + aliases:
                        if not can:
                            continue
                        if can in s_l:
                            if contains_negation(s_l, can, cues):
                                continue
                            c.execute("INSERT INTO kb_symptoms VALUES (?,?,?,?,?)",
                                      (hadm_id, rowid, s, eng, kor))
                            break
        c.execute("CREATE INDEX IF NOT EXISTS idx_kbs_hadm ON kb_symptoms(hadm_id)")

        # triples
        c.execute("DROP TABLE IF EXISTS kb_triples")
        c.execute("""
            CREATE TABLE kb_triples AS
            SELECT DISTINCT kbc.hadm_id, kbc.icd9_code, kbc.cond_name,
                            kbs.symptom_kor AS symptom, kbt.drug
            FROM kb_conditions kbc
            LEFT JOIN kb_symptoms kbs ON kbc.hadm_id = kbs.hadm_id
            LEFT JOIN kb_treatments kbt ON kbc.hadm_id = kbt.hadm_id
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_kbtp_hadm ON kb_triples(hadm_id)")

        print("[KB] tables built (negation/lexicon applied)")
