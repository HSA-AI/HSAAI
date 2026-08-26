from backend_core.db.database import SessionLocal
from backend_core.db.models import Message

def save_message(user: str, role: str, message: str, workspace_id: str = "default", agent: str = "general") -> None:
    db = SessionLocal()
    try:
        db.add(Message(user=user, role=role, message=message, workspace_id=workspace_id, agent=agent))
        db.commit()
    finally:
        db.close()

def get_history(user: str, workspace_id: str = "default", limit: int = 50):
    db = SessionLocal()
    try:
        q = db.query(Message).filter(Message.user == user, Message.workspace_id == workspace_id).order_by(Message.id.desc()).limit(limit)
        return list(reversed(q.all()))
    finally:
        db.close()
