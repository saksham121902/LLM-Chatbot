from pydantic import BaseModel, Field, field_validator
from typing import Optional


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=4000)
    system_prompt: Optional[str] = None

    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("message cannot be empty after trimming")
        if len(trimmed) > 4000:
            raise ValueError("message cannot exceed 4000 characters")
        return trimmed


class MessageMetadata(BaseModel):
    resolution_source: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: Optional[str]
    fallback_attempts: int


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: MessageMetadata


class HistoryMessage(BaseModel):
    role: str
    content: str
    metadata: Optional[MessageMetadata] = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]
