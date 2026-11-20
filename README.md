# MIMIC 의료 RAG 에이전트 (한국어 질의)

> 2025 개인 프로젝트 · MIMIC 임상 데이터를 근거로 한국어 질문에 답하는 의료 RAG 에이전트
> 한이음 드림업 프로젝트(디지털 홈케어 로봇)의 **AI 메디컬 어시스턴트 모듈**로도 활용

한국어로 증상·질환·검사를 물으면, 영문 임상 노트와 구조화 데이터(진단·처방·검사)에서 근거를 찾아 **근거 출처가 붙은 JSON 형식**으로 한국어 답변을 만듭니다.

## 핵심 요약

- MIMIC CSV를 **SQLite**로 적재하고, 임상 노트를 청크로 나눠 **FAISS(의미 검색)** 와 **BM25(키워드 검색)** 인덱스를 함께 만듭니다.
- 두 검색 결과를 노트 기준으로 합치고 점수를 가중 결합하는 **하이브리드 검색**(BM25 0.35 · 벡터 0.65)으로 근거를 고릅니다.
- 노트에서 증상을 뽑을 때 `no / denies / without` 같은 **부정 표현을 제외**해(NegEx 방식의 단순 규칙) 진단–증상–치료 지식을 만듭니다.
- 답변은 **pydantic 스키마**로 `answer · bullets · citations · disclaimer` 필드를 보장하고, LLM 키가 없으면 검색 결과만으로 요약합니다.

## 아키텍처

```
[전처리: cli build_all]
MIMIC CSV ─▶ ingest.py ─▶ SQLite (admissions, diagnoses, prescriptions, labevents, noteevents …)
                │
                ├─▶ build_kb.py   ─▶ 진단–증상–치료 트리플 (증상 사전 + 부정 표현 제외)
                ├─▶ index_notes.py ─▶ 노트 청크 → multilingual MiniLM 임베딩 → FAISS
                └─▶ bm25_index.py  ─▶ BM25 인덱스

[질의: cli query "기침과 발열 환자에서 의심 질병은?"]
한국어 질문 ─▶ Retriever.hybrid ─▶ FAISS + BM25 점수 결합 ─▶ 상위 입원(HADM) 선택
          ─▶ 해당 입원의 진단·치료·증상 KB 조회 ─▶ 근거 묶음(JSON)
          ─▶ answerer: OpenAI / Gemini (선택) ─▶ AnswerJSON 검증  (키 없으면 근거 기반 요약)
```

## 구현 포인트

| 영역 | 구현 내용 | 관련 파일 |
|---|---|---|
| 적재 | 필요한 8개 테이블을 SQLite로 옮기고 HADM·코드 기준 인덱스 생성 | `ingest.py` |
| 지식베이스 | 증상 사전(영문·한국어·동의어)과 부정 표현 목록으로 노트 문장에서 증상 추출, 진단·처방과 묶어 트리플 생성 | `build_kb.py`, `artifacts/` |
| 벡터 검색 | 노트를 약 700토큰 단위로 청크, `paraphrase-multilingual-MiniLM-L12-v2` 임베딩, FAISS 내적 인덱스 | `index_notes.py`, `retriever.py` |
| 하이브리드 | BM25·벡터 결과를 노트 기준으로 병합해 가중합(0.35 : 0.65), 상위 입원(HADM) 순서 결정. 노트 종류별 가중(`ranker.py`)은 실험용으로 따로 작성 | `retriever.py`, `ranker.py` |
| 검사 요약 | WBC·Hb·Na·K·Cr 최근 측정값을 기준 범위와 비교해 이상치를 한국어로 요약 | `labs.py`, `artifacts/lab_ranges.json` |
| 출력 검증 | 시스템 프롬프트로 "근거 안에서만, JSON만" 규칙을 주고 pydantic으로 검증 | `prompts.py`, `schema.py`, `answerer.py` |
| CLI | `build_all` · `query` · `hadm_summary` · `labs_insight` · `triples_search` | `cli.py` |

## 확인한 한계

MIMIC 데이터가 중환자실·응급실 중심이라, 기침·발열 같은 **가벼운 증상 질문에서는 검색 결과가 잘 맞지 않는 문제**를 확인했습니다. 정량 평가 기록은 남기지 않았습니다. 설계 내용은 [`docs/MIMIC_의료_RAG_에이전트_구축_보고서.pdf`](docs/)에 정리했습니다.

## 프로젝트 구조

```
mimic_rag_agent/
├─ ingest.py        CSV → SQLite 적재
├─ build_kb.py      진단-증상-치료 트리플 생성
├─ index_notes.py   노트 청킹 + FAISS 인덱스
├─ bm25_index.py    BM25 인덱스
├─ retriever.py     하이브리드 검색
├─ ranker.py        노트 종류별 가중 실험 (현재 검색 경로에는 미연결)
├─ labs.py          검사 이상치 분석
├─ answerer.py      LLM 답변 생성 / 폴백 요약
└─ cli.py          명령행 인터페이스
artifacts/          증상 사전, 부정 표현, 검사 기준 범위
docs/               설계 보고서
```

## 빠른 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# PhysioNet에서 MIMIC-III Clinical Database Demo를 받아 data/mimic_demo/ 에 배치
python -m mimic_rag_agent.cli build_all
python -m mimic_rag_agent.cli query "기침과 발열 환자에서 의심 질병은?" --top_k 5
python -m mimic_rag_agent.cli labs_insight --hadm_id 123456
```

## 기술 스택

Python · SQLite · FAISS · rank-bm25 · sentence-transformers · pandas · pydantic · OpenAI / Gemini API

## 공개 범위

MIMIC 데이터는 PhysioNet 라이선스 조건에 따라 포함하지 않았습니다. [PhysioNet](https://physionet.org/content/mimiciii-demo/)에서 직접 받아 주세요.
