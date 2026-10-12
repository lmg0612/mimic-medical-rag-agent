import os, pickle
from tqdm import tqdm
from rank_bm25 import BM25Okapi
from .config import SQLITE_PATH, BM25_PATH
from .utils import sqlite_conn, simple_tokenize_en, sentence_split

def run():
    texts, metas, toks = [], [], []
    with sqlite_conn(SQLITE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT rowid, hadm_id, category, chartdate, text FROM noteevents")
        for rowid, hadm_id, category, chartdate, txt in tqdm(cur.fetchall(), desc="[BM25] chunking"):
            if not txt: continue
            # 간단: 문단 단위로
            for para in txt.split('\n\n'):
                p = (para or "").strip()
                if not p: continue
                texts.append(p)
                metas.append({"note_rowid":rowid,"hadm_id":hadm_id,"category":category,"chartdate":chartdate})
                toks.append(simple_tokenize_en(p))
    if not texts:
        print("[BM25] no docs")
        return
    bm25 = BM25Okapi(toks)
    with open(BM25_PATH, "wb") as f:
        pickle.dump({"bm25": bm25, "texts": texts, "metas": metas}, f)
    print(f"[BM25] 저장 완료: {len(texts)} docs")
