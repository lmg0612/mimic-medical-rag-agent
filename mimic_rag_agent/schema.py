from pydantic import BaseModel, Field
from typing import List, Dict, Any

class Citation(BaseModel):
    type: str
    hadm_id: int | None = None
    note_rowid: int | None = None
    field: str | None = None

class AnswerJSON(BaseModel):
    answer: str = Field(default="")
    bullets: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    disclaimer: str = Field(default="이 정보는 의료 조언이 아닙니다.")
