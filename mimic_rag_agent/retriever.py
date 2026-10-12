import os, pickle, sqlite3, numpy as np
from typing import List, Dict, Any
from .config import SQLITE_PATH, FAISS_DIR, BM25_PATH

# faiss 사용 가능 여부 점검
try:
    import faiss  # type: ignore
    FAISS_AVAILABLE = True
except Exception:
    FAISS_AVAILABLE = False

class Retriever:
    def __init__(self, top_k:int=5):
        self.top_k = top_k

        # 벡터 인덱스 로드 (없으면 비활성)
        self.vec_enabled = False
        self.vec_texts, self.vec_metas, self.index = [], [], None
        meta_p = os.path.join(FAISS_DIR, "meta.pkl")
        index_p = os.path.join(FAISS_DIR, "notes.index")
        if FAISS_AVAILABLE and os.path.exists(meta_p) and os.path.exists(index_p):
            try:
                with open(meta_p, "rb") as f:
                    m = pickle.load(f)
                self.vec_texts = m.get("texts", [])
                self.vec_metas = m.get("metas", [])
                self.index = faiss.read_index(index_p)
                self.vec_enabled = True
            except Exception:
                self.vec_enabled = False

        # BM25 로드 (없으면 비활성)
        self.bm25_enabled = False
        self.bm25 = None
        self.bm_texts, self.bm_metas = [], []
        if os.path.exists(BM25_PATH):
            try:
                with open(BM25_PATH, "rb") as f:
                    b = pickle.load(f)
                self.bm25 = b["bm25"]
                self.bm_texts = b["texts"]
                self.bm_metas = b["metas"]
                self.bm25_enabled = True
            except Exception:
                self.bm25_enabled = False

    def vector_search(self, query: str, k: int=None):
        if not self.vec_enabled:
            return []
        k = k or self.top_k
        # NOTE: 인덱스가 만들어질 때 임베딩이 이미 계산되어 있으므로 여긴 질의 임베딩만 필요.
        # 하지만 sentence-transformers가 필요하므로, 인덱스가 있을 때만 사용 (없으면 빈 리스트)
        try:
            from sentence_transformers import SentenceTransformer
            # 인덱스 만들 때 썼던 모델이 동일 경로일 필요는 없음(동일 차원이어야 함)
            model = SentenceTransformer(os.getenv("EMBEDDING_MODEL","sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"))
            q = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
            D, I = self.index.search(q, k)
            res = []
            for score, idx in zip(D[0].tolist(), I[0].tolist()):
                if idx < 0: 
                    continue
                res.append({"score": float(score), "text": self.vec_texts[idx], "meta": self.vec_metas[idx]})
            return res
        except Exception:
            return []

    def bm25_search(self, query: str, k: int=None):
        if not self.bm25_enabled:
            return []
        import re
        k = k or self.top_k
        toks = re.findall(r"[A-Za-z0-9]+", (query or "").lower())
        scores = self.bm25.get_scores(toks)
        idxs = np.argsort(scores)[-k:][::-1]
        res = []
        for i in idxs:
            res.append({"score": float(scores[i]), "text": self.bm_texts[i], "meta": self.bm_metas[i]})
        return res

    def kb_from_hadm(self, hadm_ids: List[int]):
        with sqlite3.connect(SQLITE_PATH) as conn:
            c = conn.cursor()
            qmarks = ",".join(["?"]*len(hadm_ids)) if hadm_ids else "NULL"
            conds, treats, syms = [], [], []
            if hadm_ids:
                for r in c.execute(f"SELECT hadm_id, icd9_code, cond_name FROM kb_conditions WHERE hadm_id IN ({qmarks})", hadm_ids):
                    conds.append({"hadm_id": r[0], "code": r[1], "name": r[2]})
                for r in c.execute(f"SELECT hadm_id, drug, dose_val, dose_unit, route FROM kb_treatments WHERE hadm_id IN ({qmarks})", hadm_ids):
                    treats.append({"hadm_id": r[0], "drug": r[1], "dose": r[2], "unit": r[3], "route": r[4]})
                for r in c.execute(f"SELECT hadm_id, symptom_kor FROM kb_symptoms WHERE hadm_id IN ({qmarks})", hadm_ids):
                    syms.append({"hadm_id": r[0], "symptom": r[1]})
        return conds, treats, syms

    def kb_fallback_candidates(self, k:int):
        # 노트 인덱스가 없을 때: 가장 정보가 많은 입원 에피소드 상위 k개를 고름
        with sqlite3.connect(SQLITE_PATH) as conn:
            c = conn.cursor()
            # 1) 진단 수 기준 TOP hadm
            rows = list(c.execute("""
                SELECT hadm_id, COUNT(*) AS n
                FROM kb_conditions
                GROUP BY hadm_id
                ORDER BY n DESC
                LIMIT ?
            """, (k,)))
            hadm_ids = [r[0] for r in rows]
            if len(hadm_ids) < k:
                # 2) 처방 수로 보강
                more = list(c.execute("""
                    SELECT hadm_id, COUNT(*) AS n
                    FROM kb_treatments
                    GROUP BY hadm_id
                    ORDER BY n DESC
                    LIMIT ?
                """, (k*2,)))
                for hid, _ in more:
                    if hid not in hadm_ids:
                        hadm_ids.append(hid)
                        if len(hadm_ids) >= k:
                            break
        return hadm_ids[:k]

    def hybrid(self, query: str, k: int=None):
        k = k or self.top_k
        v = self.vector_search(query, k=k*3) if self.vec_enabled else []
        b = self.bm25_search(query, k=k*3)   if self.bm25_enabled else []

        items = []
        if v or b:
            # 간단 병합
            pool = {}
            for r in b:
                key = (r["text"][:80], r["meta"]["note_rowid"])
                pool[key] = {"bm": r["score"], "vec": 0.0, "text": r["text"], "meta": r["meta"]}
            for r in v:
                key = (r["text"][:80], r["meta"]["note_rowid"])
                if key in pool:
                    pool[key]["vec"] = max(pool[key]["vec"], r["score"])
                else:
                    pool[key] = {"bm":0.0, "vec": r["score"], "text": r["text"], "meta": r["meta"]}
            for v in pool.values():
                score = 0.35*v["bm"] + 0.65*v["vec"]
                items.append({"score": float(score), "text": v["text"], "meta": v["meta"], "bm25": v["bm"], "vec": v["vec"]})
            items.sort(key=lambda x: -x["score"])
            hadm_seen, hadm_rank = set(), []
            for it in items:
                hid = it["meta"]["hadm_id"]
                if hid not in hadm_seen:
                    hadm_rank.append(hid); hadm_seen.add(hid)
        else:
            # 인덱스가 전혀 없으면 KB만으로 후보 hadm 선택
            hadm_rank = self.kb_fallback_candidates(k)
            items = []  # 노트 없음

        conds, treats, syms = self.kb_from_hadm(hadm_rank[:k])
        return {"notes": items[:k], "conditions": conds, "treatments": treats, "symptoms": syms}
