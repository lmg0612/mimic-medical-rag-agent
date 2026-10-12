import argparse, json
from . import ingest, build_kb, index_notes, bm25_index
from .retriever import Retriever
from .answerer import answer
from .labs import per_hadm_latest
from .config import OPENAI_API_KEY, GEMINI_API_KEY

def build_all():
    ingest.run()
    build_kb.run()
    index_notes.run()
    bm25_index.run()

def cmd_query(args):
    retr = Retriever(top_k=args.top_k)
    bundle = retr.hybrid(args.text, k=args.top_k)
    out = answer(args.text, bundle, llm_provider=args.llm.lower() if args.llm else "", api_keys={
        "openai": OPENAI_API_KEY, "gemini": GEMINI_API_KEY
    })
    print(json.dumps(out, ensure_ascii=False, indent=2))

def cmd_hadm_summary(args):
    retr = Retriever(top_k=args.top_k)
    # 간단: 관련 노트 우선 검색하여 해당 hadm 근거 묶음 생성
    bundle = retr.hybrid(f"hadm:{args.hadm_id}", k=args.top_k)
    # hadm 강제 필터
    hadm = int(args.hadm_id)
    bundle["notes"] = [n for n in bundle["notes"] if n["meta"]["hadm_id"]==hadm]
    bundle["conditions"] = [c for c in bundle["conditions"] if c["hadm_id"]==hadm]
    bundle["treatments"] = [t for t in bundle["treatments"] if t["hadm_id"]==hadm]
    bundle["symptoms"] = [s for s in bundle["symptoms"] if s["hadm_id"]==hadm]
    out = answer(f"HADM {hadm} 입원 요약", bundle, llm_provider=args.llm.lower() if args.llm else "", api_keys={
        "openai": OPENAI_API_KEY, "gemini": GEMINI_API_KEY
    })
    print(json.dumps(out, ensure_ascii=False, indent=2))

def cmd_labs_insight(args):
    hadm = int(args.hadm_id)
    labs = per_hadm_latest(hadm)
    out = {
        "answer":"대표 검사 항목의 최신 상태를 요약했습니다.",
        "bullets":[f"{x['code']}: {x['value']}{x['unit']} ({x['assessment']}, 범위 {x['range']['low']}–{x['range']['high']})" for x in labs],
        "citations":[{"type":"lab","hadm_id":hadm}],
        "disclaimer":"이 정보는 연구용 데모에서 생성되었으며 의료 조언이 아닙니다."
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

def cmd_triples_search(args):
    retr = Retriever(top_k=args.top_k)
    # 단순 구현: 전체 KB에서 텍스트 포함 매칭
    import sqlite3
    from .config import SQLITE_PATH
    conn = sqlite3.connect(SQLITE_PATH); c=conn.cursor()
    rows = []
    if args.condition_kor:
        q = f"%{args.condition_kor}%"
        # cond_name은 영문 → 부분 일치
        rows = list(c.execute("SELECT hadm_id, icd9_code, cond_name, symptom, drug FROM kb_triples WHERE cond_name LIKE ? LIMIT ?", (q, args.top_k)))
    elif args.symptom_kor:
        q = f"%{args.symptom_kor}%"
        rows = list(c.execute("SELECT hadm_id, icd9_code, cond_name, symptom, drug FROM kb_triples WHERE symptom LIKE ? LIMIT ?", (q, args.top_k)))
    elif args.drug:
        q = f"%{args.drug}%"
        rows = list(c.execute("SELECT hadm_id, icd9_code, cond_name, symptom, drug FROM kb_triples WHERE drug LIKE ? LIMIT ?", (q, args.top_k)))
    out = {
        "answer": "KB에서 조건에 맞는 (진단-증상-치료) 트리플을 조회했습니다.",
        "bullets": [f"HADM {r[0]} | {r[2]} | 증상:{r[3]} | 약물:{r[4]}" for r in rows],
        "citations": [{"type":"kb","hadm_id": r[0]} for r in rows],
        "disclaimer":"이 정보는 연구용 데모에서 생성되었으며 의료 조언이 아닙니다."
    }
    conn.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))

def main():
    import argparse
    ap = argparse.ArgumentParser(description="MIMIC KOR RAG Agent — PLUS")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("build_all", help="CSV→SQLite→KB→FAISS→BM25 전처리 전체 실행")

    qp = sub.add_parser("query", help="한국어 질의")
    qp.add_argument("text", type=str)
    qp.add_argument("--top_k", type=int, default=5)
    qp.add_argument("--llm", type=str, default="", choices=["","openai","gemini"])

    hp = sub.add_parser("hadm_summary", help="특정 HADM 요약")
    hp.add_argument("--hadm_id", required=True)
    hp.add_argument("--top_k", type=int, default=5)
    hp.add_argument("--llm", type=str, default="", choices=["","openai","gemini"])

    lp = sub.add_parser("labs_insight", help="검사 요약")
    lp.add_argument("--hadm_id", required=True)

    tp = sub.add_parser("triples_search", help="KB 트리플 검색")
    tp.add_argument("--condition_kor", type=str, default="")
    tp.add_argument("--symptom_kor", type=str, default="")
    tp.add_argument("--drug", type=str, default="")
    tp.add_argument("--top_k", type=int, default=5)

    args = ap.parse_args()
    if args.cmd == "build_all":
        build_all()
    elif args.cmd == "query":
        cmd_query(args)
    elif args.cmd == "hadm_summary":
        cmd_hadm_summary(args)
    elif args.cmd == "labs_insight":
        cmd_labs_insight(args)
    elif args.cmd == "triples_search":
        cmd_triples_search(args)
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
