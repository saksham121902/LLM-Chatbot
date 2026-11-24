from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import json
from datetime import datetime

from app.config import settings
from app.database import init_db, get_db, Message
from app.schemas import ChatRequest, ChatResponse, SessionHistoryResponse, MessageMetadata
from app.llm_service import llm_router

app = FastAPI(title="LLM Chatbot API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Test database connectivity
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "keys_configured": len(settings.api_keys_list),
            "cache_enabled": settings.cache_enabled
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail="database unreachable")


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    x_simulate_failure: Optional[str] = Header(None)
):
    """
    Chat endpoint with multi-turn context, caching, and failover.
    """
    try:
        # Parse simulation header if present
        simulate_failures = None
        if x_simulate_failure and settings.enable_failure_simulation:
            simulate_failures = {}
            for pair in x_simulate_failure.split(","):
                pair = pair.strip()
                if "=" in pair:
                    key, status = pair.split("=", 1)
                    simulate_failures[key.strip()] = int(status.strip())

        # Retrieve session history
        history = db.query(Message).filter(
            Message.session_id == request.session_id
        ).order_by(Message.id).all()

        # Build messages for LLM
        messages = []

        # Add system prompt
        system_prompt = request.system_prompt or "You are a helpful assistant."
        messages.append({"role": "system", "content": system_prompt})

        # Add history
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Add new user message
        messages.append({"role": "user", "content": request.message})

        # Call LLM with failover
        try:
            reply, metadata = await llm_router.chat_completion(messages, simulate_failures)
        except Exception:
            raise HTTPException(status_code=503, detail="all providers unavailable")

        # Store user message
        user_msg = Message(
            session_id=request.session_id,
            role="user",
            content=request.message,
            msg_metadata=None,
            created_at=datetime.utcnow().isoformat()
        )
        db.add(user_msg)

        # Store assistant message with metadata
        assistant_msg = Message(
            session_id=request.session_id,
            role="assistant",
            content=reply,
            msg_metadata=json.dumps(metadata),
            created_at=datetime.utcnow().isoformat()
        )
        db.add(assistant_msg)
        db.commit()

        return ChatResponse(
            session_id=request.session_id,
            reply=reply,
            metadata=MessageMetadata(**metadata)
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str, db: Session = Depends(get_db)):
    """
    Retrieve session history from SQLite.
    """
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.id).all()

    if not messages:
        raise HTTPException(status_code=404, detail="session not found")

    return SessionHistoryResponse(
        session_id=session_id,
        messages=[msg.to_dict() for msg in messages]
    )
