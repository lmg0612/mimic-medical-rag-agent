import os, json
from typing import Dict, Any, List
from .korean import normalize_query_kor
from .prompts import SYSTEM_PROMPT
from .schema import AnswerJSON, Citation

def _try_openai(prompt: str, api_key: str):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":prompt}],
            temperature=0.2
        )
        return resp.choices[0].message.content
    except Exception:
        return None

def _try_gemini(prompt: str, api_key: str):
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(prompt)
        return resp.text
    except Exception:
        return None

def _format_evidence(query:str, bundle:Dict[str,Any]) -> str:
    small = {
        "query": query,
        "notes": [
            {"hadm_id": n["meta"]["hadm_id"], "note_rowid": n["meta"]["note_rowid"], "snippet": n["text"][:900]}
            for n in bundle.get("notes", [])[:12]
        ],
        "kb": {
            "conditions": bundle.get("conditions", [])[:12],
            "treatments": bundle.get("treatments", [])[:12],
            "symptoms": bundle.get("symptoms", [])[:18]
        }
    }
    return json.dumps(small, ensure_ascii=False)

def _fallback(bundle:Dict[str,Any])->Dict[str,Any]:
    # 근거 집계 → 한국어 요약(JSON)
    conds, treats, syms = {}, {}, {}
    for c in bundle.get("conditions", []):
        key = c.get("name") or c.get("code")
        if key: conds[key] = conds.get(key,0)+1
    for t in bundle.get("treatments", []):
        key = (t.get("drug") or "").strip()
        if key: treats[key] = treats.get(key,0)+1
    for s in bundle.get("symptoms", []):
        key = s.get("symptom")
        if key: syms[key] = syms.get(key,0)+1

    bullets = []
    if conds: bullets.append("자주 등장하는 진단: " + ", ".join([k for k,_ in sorted(conds.items(), key=lambda x:-x[1])[:5]]))
    if syms:  bullets.append("자주 언급되는 증상: " + ", ".join([k for k,_ in sorted(syms.items(), key=lambda x:-x[1])[:7]]))
    if treats: bullets.append("자주 사용되는 약물/치료: " + ", ".join([k for k,_ in sorted(treats.items(), key=lambda x:-x[1])[:7]]))

    cits: List[Dict[str,Any]] = []
    for n in bundle.get("notes", [])[:6]:
        cits.append({"type":"note","hadm_id":n["meta"]["hadm_id"],"note_rowid":n["meta"]["note_rowid"]})
    for t in bundle.get("treatments", [])[:6]:
        cits.append({"type":"kb","hadm_id":t["hadm_id"],"field":"drug"})
    for c in bundle.get("conditions", [])[:6]:
        cits.append({"type":"kb","hadm_id":c["hadm_id"],"field":"condition"})

    model_out = {
        "answer": "질의와 유사한 입원 사례의 진단·증상·치료 패턴을 요약했습니다.",
        "bullets": bullets or ["데모 데이터에서 두드러진 패턴을 찾지 못했습니다."],
        "citations": cits,
        "disclaimer": "이 정보는 연구용 데모에서 생성되었으며 의료 조언이 아닙니다."
    }
    return AnswerJSON(**model_out).model_dump()

def answer(query_kor:str, bundle:Dict[str,Any], llm_provider:str="", api_keys:dict=None)->Dict[str,Any]:
    q = normalize_query_kor(query_kor)
    if llm_provider:
        ev = _format_evidence(q, bundle)
        prompt = f"질문: {q}\n\n근거(JSON):\n{ev}"
        if llm_provider.lower()=="openai" and api_keys.get("openai"):
            out = _try_openai(prompt, api_keys["openai"])
            if out:
                try:
                    return AnswerJSON.model_validate_json(out).model_dump()
                except Exception:
                    pass
        if llm_provider.lower()=="gemini" and api_keys.get("gemini"):
            out = _try_gemini(prompt, api_keys["gemini"])
            if out:
                try:
                    return AnswerJSON.model_validate_json(out).model_dump()
                except Exception:
                    pass
    return _fallback(bundle)
