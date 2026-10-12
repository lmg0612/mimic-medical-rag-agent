import os, sqlite3, re, pickle, json
from contextlib import contextmanager

@contextmanager
def sqlite_conn(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()

def sentence_split(text: str):
    if not text:
        return []
    text = re.sub(r'\s+', ' ', str(text)).strip()
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    return [s for s in sents if s]

def simple_tokenize_en(text: str):
    # 알파벳/숫자 토큰 (BM25용)
    return re.findall(r"[A-Za-z0-9]+", (text or "").lower())

def safe_lower(s: str):
    return s.lower() if isinstance(s, str) else s

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
