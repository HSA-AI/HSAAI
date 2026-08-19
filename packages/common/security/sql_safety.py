"""
HSAAI SQL Safety Layer (Phase 30)
===================================
Allow-list based SQL construction. Prevents SQL injection by:
1. Validating column names against a known allow-list
2. Validating table names against a known allow-list
3. Validating sort direction (ASC/DESC only)
4. Validating limit/offset as integers
5. Using parameterized queries for all values

Usage:
    from packages.common.security.sql_safety import SafeQueryBuilder

    qb = SafeQueryBuilder()
    qb.table("documents")
    qb.select(["document_id", "title", "content"])
    qb.where("tenant_id", "=", tenant_id)  # parameterized
    qb.where("category", "=", category)
    qb.order_by("created_at", "DESC")
    qb.limit(50)

    sql, params = qb.build()
    # SELECT document_id, title, content FROM documents
    # WHERE tenant_id = %s AND category = %s
    # ORDER BY created_at DESC LIMIT 50
    # params: (tenant_id, category)
"""
import re
from typing import Any, List, Optional, Tuple


class SQLSafetyError(Exception):
    """Raised when unsafe SQL construction is attempted."""


# ─── ALLOW-LISTS ──────────────────────────────────────────────────
ALLOWED_TABLES = {
    "tenants", "users", "documents", "episodic_memories",
    "procedural_memories", "audit_log", "agents", "workflows",
    "tasks", "notifications", "chats", "messages",
    "approvals", "connectors", "model_runs",
}

ALLOWED_COLUMNS = {
    # Common
    "id", "tenant_id", "created_at", "updated_at", "deleted_at",
    "metadata", "is_active",
    # Users
    "user_id", "email", "full_name", "role", "last_login",
    # Documents
    "document_id", "title", "content", "category", "language", "source", "checksum",
    # Memories
    "memory_id", "agent_id", "importance", "last_accessed", "access_count", "tags",
    # Audit
    "audit_id", "timestamp", "action", "decision", "reason", "request_id",
    # Agents
    "agent_id", "name", "description", "status", "last_run", "success_rate",
    # Workflows
    "workflow_id", "current_step", "started_at", "completed_at",
    # Tasks
    "task_id", "assigned_to", "due_date", "priority",
    # Notifications
    "notification_id", "type", "is_read",
    # Chats
    "chat_id", "model", "tokens_used", "latency_ms",
    # Approvals
    "request_id", "severity", "approved_by", "required_approvals",
    # Connectors
    "connector_name", "connector_type", "last_sync",
    # Model runs
    "run_id", "model_name", "tokens_input", "tokens_output",
}

ALLOWED_OPERATORS = {"=", "!=", "<", ">", "<=", ">=", "LIKE", "ILIKE", "IN", "IS", "IS NOT"}

ALLOWED_SORT_DIRECTIONS = {"ASC", "DESC"}


class SafeQueryBuilder:
    """
    Builds SQL queries with allow-list validation.
    All user input is parameterized — no string interpolation.
    """

    def __init__(self):
        self._table: Optional[str] = None
        self._select: List[str] = ["*"]
        self._where_clauses: List[str] = []
        self._params: List[Any] = []
        self._order_by: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None

    def table(self, name: str) -> "SafeQueryBuilder":
        """Set the table name (validated against allow-list)."""
        if name not in ALLOWED_TABLES:
            raise SQLSafetyError(f"Table '{name}' not in allow-list. Allowed: {ALLOWED_TABLES}")
        self._table = name
        return self

    def select(self, columns: List[str]) -> "SafeQueryBuilder":
        """Set SELECT columns (validated against allow-list)."""
        for col in columns:
            if col != "*" and col not in ALLOWED_COLUMNS:
                raise SQLSafetyError(f"Column '{col}' not in allow-list")
        self._select = columns
        return self

    def where(self, column: str, operator: str, value: Any) -> "SafeQueryBuilder":
        """Add a WHERE clause (parameterized)."""
        if column not in ALLOWED_COLUMNS:
            raise SQLSafetyError(f"Column '{column}' not in allow-list")
        if operator.upper() not in ALLOWED_OPERATORS:
            raise SQLSafetyError(f"Operator '{operator}' not allowed. Use: {ALLOWED_OPERATORS}")

        if operator.upper() == "IN":
            if not isinstance(value, (list, tuple)):
                raise SQLSafetyError("IN operator requires list/tuple value")
            placeholders = ", ".join(["%s"] * len(value))
            self._where_clauses.append(f"{column} IN ({placeholders})")
            self._params.extend(value)
        elif operator.upper() in ("IS", "IS NOT"):
            if value not in (None, True, False):
                raise SQLSafetyError("IS operator requires None/True/False")
            self._where_clauses.append(f"{column} {operator} {'NULL' if value is None else value}")
        else:
            self._where_clauses.append(f"{column} {operator} %s")
            self._params.append(value)
        return self

    def order_by(self, column: str, direction: str = "ASC") -> "SafeQueryBuilder":
        """Add ORDER BY (validated column + direction)."""
        if column not in ALLOWED_COLUMNS:
            raise SQLSafetyError(f"Column '{column}' not in allow-list")
        direction = direction.upper()
        if direction not in ALLOWED_SORT_DIRECTIONS:
            raise SQLSafetyError(f"Sort direction must be ASC or DESC, got: {direction}")
        self._order_by = f"{column} {direction}"
        return self

    def limit(self, value: int) -> "SafeQueryBuilder":
        """Set LIMIT (validated as integer, max 1000)."""
        if not isinstance(value, int) or value < 1 or value > 1000:
            raise SQLSafetyError("LIMIT must be integer 1-1000")
        self._limit = value
        return self

    def offset(self, value: int) -> "SafeQueryBuilder":
        """Set OFFSET (validated as integer, max 1M)."""
        if not isinstance(value, int) or value < 0 or value > 1_000_000:
            raise SQLSafetyError("OFFSET must be integer 0-1000000")
        self._offset = value
        return self

    def build(self) -> Tuple[str, Tuple]:
        """Build the SQL query and parameters. Returns (sql, params)."""
        if not self._table:
            raise SQLSafetyError("Table not set")

        cols = ", ".join(self._select)
        sql = f"SELECT {cols} FROM {self._table}"

        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)

        if self._order_by:
            sql += f" ORDER BY {self._order_by}"

        if self._limit:
            sql += f" LIMIT {self._limit}"

        if self._offset:
            sql += f" OFFSET {self._offset}"

        return sql, tuple(self._params)


def sanitize_identifier(name: str, allow_list: set) -> str:
    """
    Sanitize a SQL identifier (table/column name) against an allow-list.
    Returns the name if safe, raises SQLSafetyError otherwise.
    """
    # Whitelist characters: alphanumeric + underscore
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise SQLSafetyError(f"Invalid identifier: {name}")
    if name not in allow_list:
        raise SQLSafetyError(f"Identifier '{name}' not in allow-list")
    return name


def validate_search_query(query: str, max_length: int = 1000) -> str:
    """
    Validate a search query for safe use in LIKE/ILIKE clauses.
    Escapes special SQL LIKE characters.
    """
    if len(query) > max_length:
        raise SQLSafetyError(f"Query exceeds max length {max_length}")
    # Escape LIKE special characters
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
