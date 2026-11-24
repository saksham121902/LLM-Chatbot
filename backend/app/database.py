import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json
from app.config import settings

Base = declarative_base()


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    msg_metadata = Column("metadata", Text, nullable=True)  # JSON string for assistant messages
    created_at = Column(String(30), nullable=False)  # ISO-8601
    
    def to_dict(self):
        result = {
            "role": self.role,
            "content": self.content
        }
        if self.msg_metadata:
            result["metadata"] = json.loads(self.msg_metadata)
        return result


def _resolve_database_url() -> str:
    db_url = settings.database_url
    if db_url.startswith("sqlite:////"):
        filepath = db_url.replace("sqlite:////", "/")
        dirpath = os.path.dirname(filepath)
        if dirpath and not os.path.exists(dirpath):
            try:
                os.makedirs(dirpath, exist_ok=True)
            except Exception:
                return "sqlite:///./app.db"
    return db_url


# Database engine
effective_db_url = _resolve_database_url()
engine = create_engine(
    effective_db_url,
    connect_args={"check_same_thread": False} if "sqlite" in effective_db_url else {}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
