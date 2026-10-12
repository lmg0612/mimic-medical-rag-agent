from typing import List, Dict, Any
from .config import ALPHA_BM25, BETA_VECTOR, GAMMA_META

def meta_boost(m:Dict[str,Any]):
    # 카테고리/최근성 등 단순 가중
    cat = (m.get("category") or "").lower()
    boost = 0.0
    if "discharge" in cat:
        boost += 0.05
    if "radiology" in cat:
        boost += 0.02
    # 날짜 정보 가중(최근성), 데모에서는 제한적
    return boost

def blend_scores(bm25_res, vec_res, top_k:int):
    # 결과 병합(간단): 텍스트 동일성 기준 병합
    pool = {}
    for r in bm25_res:
        key = (r["text"][:60], r["meta"]["note_rowid"])
        pool[key] = {"text":r["text"], "meta":r["meta"], "bm25":r["score"], "vec":0.0}
    for r in vec_res:
        key = (r["text"][:60], r["meta"]["note_rowid"])
        if key not in pool:
            pool[key] = {"text":r["text"], "meta":r["meta"], "bm25":0.0, "vec":r["score"]}
        else:
            pool[key]["vec"] = max(pool[key]["vec"], r["score"])

    items = []
    for v in pool.values():
        mb = meta_boost(v["meta"])
        final = ALPHA_BM25*v["bm25"] + BETA_VECTOR*v["vec"] + GAMMA_META*mb
        items.append({"score":final, "text":v["text"], "meta":v["meta"], "bm25":v["bm25"], "vec":v["vec"], "meta_boost":mb})
    items.sort(key=lambda x: -x["score"])
    return items[:top_k]
