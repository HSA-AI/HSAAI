from backend_core.db.database import SessionLocal
from backend_core.db.models import Message

def save_message(user: str, role: str, message: str, workspace_id: str = "default", agent: str = "general", tenant_id: str = "default") -> None:
    """FIX (P0 runtime): Message.tenant_id is NOT NULL in the schema, but this
    helper never accepted or passed it — every chat INSERT failed with
    `sqlite3.IntegrityError: NOT NULL constraint failed: messages.tenant_id`
    (and the same failure on PostgreSQL). Optional kwarg keeps every existing
    caller working (defaults to 'default')."""
    db = SessionLocal()
    try:
        db.add(Message(user=user, role=role, message=message, workspace_id=workspace_id, agent=agent, tenant_id=tenant_id))
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
