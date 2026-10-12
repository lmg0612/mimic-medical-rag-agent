import os, pickle
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import faiss

from .config import SQLITE_PATH, FAISS_DIR, EMBEDDING_MODEL
from .utils import sqlite_conn, sentence_split

os.makedirs(FAISS_DIR, exist_ok=True)

def _chunk(text: str, max_tokens=700):
    sents = sentence_split(text)
    chunks, buf, n = [], [], 0
    for s in sents:
        ln = max(1, len(s.split()))
        if n + ln > max_tokens and buf:
            chunks.append(" ".join(buf))
            buf, n = [], 0
        buf.append(s)
        n += ln
    if buf:
        chunks.append(" ".join(buf))
    return chunks

def run():
    with sqlite_conn(SQLITE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT rowid, hadm_id, category, chartdate, text FROM noteevents")
        rows = cur.fetchall()

    texts, metas = [], []
    for rowid, hadm_id, category, chartdate, txt in tqdm(rows, desc="[INDEX] chunking"):
        if not txt: 
            continue
        for ch in _chunk(txt):
            texts.append(ch)
            metas.append({"note_rowid": rowid, "hadm_id": hadm_id, "category": category, "chartdate": chartdate})

    if not texts:
        print("[INDEX] no note chunks")
        return

    model = SentenceTransformer(EMBEDDING_MODEL)
    embs = model.encode(texts, show_progress_bar=True, convert_to_numpy=True, batch_size=64, normalize_embeddings=True)
    d = embs.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(embs)
    faiss.write_index(index, os.path.join(FAISS_DIR, "notes.index"))
    with open(os.path.join(FAISS_DIR, "meta.pkl"), "wb") as f:
        pickle.dump({"texts":texts, "metas":metas}, f)
    print(f"[INDEX] FAISS 저장: {len(texts)} chunks, dim={d}")
