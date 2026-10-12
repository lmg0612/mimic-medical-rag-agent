# MIMIC 의료 RAG 에이전트 (한국어 질의)

> 2025-2학기 개인 프로젝트 · MIMIC-III 임상 데이터를 기반으로 한국어 질문에 답하는 의료 RAG 에이전트

## 개요
한국어로 증상·질환·검사 결과를 물으면, 영문 임상 노트와 구조화 데이터(진단·처방·검사)에서 근거를 찾아 한국어로 요약 답변합니다. 한이음 드림업 프로젝트(디지털 홈케어 로봇)의 **AI 메디컬 어시스턴트 모듈**로도 활용했습니다.

## 주요 기능
- **하이브리드 검색**: FAISS(의미 검색) + BM25(키워드) 가중 결합, 가중치(α, β, γ) 조정 가능
- **부정 표현 처리**: 임상 노트의 `no / denies / without` 등 부정 맥락 제거
- **지식베이스**: 진단 ↔ 증상 ↔ 치료 트리플 생성, 한국어 라벨 매핑
- **Lab Insight**: WBC·Hb·Na·K·Cr 등 대표 검사의 정상 범위 기반 이상치 감지와 한국어 요약
- **출력 검증**: pydantic 스키마로 JSON 응답 필수 필드 보장
- **LLM 선택**: OpenAI / Gemini 선택 사용(키 없으면 검색 결과 기반 요약)

## 구조
```
mimic_rag_agent/
├─ ingest.py        # CSV → SQLite 적재
├─ build_kb.py      # 진단-증상-치료 트리플 생성
├─ index_notes.py   # 노트 청킹 + FAISS 인덱스
├─ bm25_index.py    # BM25 인덱스
├─ retriever.py     # 하이브리드 검색
├─ ranker.py        # 재순위화
├─ labs.py          # 검사 이상치 분석
├─ answerer.py      # LLM 답변 생성
└─ cli.py           # 명령행 인터페이스
artifacts/           # 증상 사전, 부정 표현, 검사 기준 범위
docs/                # 설계 보고서
```

## 실행
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# PhysioNet에서 MIMIC-III Clinical Database Demo를 받아 data/mimic_demo/ 에 배치
python -m mimic_rag_agent.cli build_all
python -m mimic_rag_agent.cli query "기침과 발열 환자에서 의심 질병은?" --top_k 5
python -m mimic_rag_agent.cli hadm_summary --hadm_id 123456
python -m mimic_rag_agent.cli labs_insight --hadm_id 123456
```

## 기술 스택
Python · FAISS · rank-bm25 · sentence-transformers · pandas · SQLite · pydantic · OpenAI / Gemini API

## 데이터
MIMIC-III 데이터는 PhysioNet 라이선스 조건에 따라 이 레포에 포함하지 않았습니다. [PhysioNet](https://physionet.org/content/mimiciii-demo/)에서 직접 받아 주세요.
