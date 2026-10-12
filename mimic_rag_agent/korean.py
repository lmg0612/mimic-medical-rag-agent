import re

def normalize_query_kor(q:str)->str:
    q = (q or "").strip()
    q = re.sub(r"\s+", " ", q)
    return q
