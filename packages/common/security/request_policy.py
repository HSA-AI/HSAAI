"""Small, dependency-free request policies shared by HSAAI services."""
from collections import OrderedDict, deque
from contextvars import ContextVar
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

tenant_context: ContextVar[str | None] = ContextVar("hsaai_tenant", default=None)
workspace_context: ContextVar[str | None] = ContextVar("hsaai_workspace", default=None)
authorization_context: ContextVar[str | None] = ContextVar("hsaai_authorization", default=None)


def verified_scope(claims: dict) -> tuple[str, str]:
    """Accept only explicit organization/workspace claims from a verified token."""
    values = (claims.get("tenant_id"), claims.get("workspace_id"))
    if any(not isinstance(v, str) or not v.strip() or len(v) > 128 for v in values):
        raise ValueError("Token requires tenant_id and workspace_id claims")
    return values


def origin_allowed(origin: str | None, allowed: list[str]) -> bool:
    if not origin or origin == "null":
        return False
    try:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            return False
        normalized = origin.rstrip("/")
        return normalized in {item.rstrip("/") for item in allowed if item != "*"}
    except ValueError:
        return False


def outgoing_headers() -> dict[str, str]:
    token = authorization_context.get()
    return {"Authorization": token} if token else {}


class SlidingWindowLimiter:
    """Bounded, thread-safe per-process fallback. Redis is required across replicas.

    When the client table is full, new clients are denied until idle entries
    expire; active clients are never evicted to permit quota bypass.
    """
    def __init__(self, limit: int, window: float = 60, max_clients: int = 10000, clock=monotonic):
        if min(limit, window, max_clients) <= 0:
            raise ValueError("Limits must be positive")
        self.limit, self.window, self.max_clients = limit, window, max_clients
        self.clock = clock
        self.buckets: OrderedDict[str, deque] = OrderedDict()
        self.lock = Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self.lock:
            while self.buckets:
                first = next(iter(self.buckets))
                if now - self.buckets[first][-1] < self.window:
                    break
                self.buckets.popitem(last=False)
            bucket = self.buckets.get(key)
            if bucket is None:
                if len(self.buckets) >= self.max_clients:
                    return False
                bucket = self.buckets[key] = deque()
            while bucket and now - bucket[0] >= self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            self.buckets.move_to_end(key)
            return True
