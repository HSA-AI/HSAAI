"""
HSAAI Agent-to-Agent (A2A) Protocol — v0.3.0

Enables agents in the Civilization to communicate, delegate,
collaborate, and negotiate with each other.

Message types:
  - task_request:  Agent A asks Agent B to do something
  - task_response: Agent B returns results
  - query:         Agent A asks Agent B for information
  - query_response: Agent B answers
  - negotiation:   Agents negotiate resource allocation
  - broadcast:     Supervisor broadcasts to all agents
"""
from __future__ import annotations
import asyncio, logging, time, uuid, json
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional
from collections import defaultdict
logger = logging.getLogger("hsaai.a2a")

@dataclass
class A2AMessage:
    message_id: str = ""
    from_agent: str = ""
    to_agent: str = ""  # "supervisor", "all", or specific agent_id
    message_type: str = ""  # task_request, task_response, query, query_response, negotiation, broadcast
    task_id: str = ""
    content: dict = field(default_factory=dict)
    priority: str = "normal"  # low, normal, high, urgent
    deadline: float = 0.0
    timestamp: float = 0.0
    trace_id: str = ""
    requires_ack: bool = True
    acked: bool = False

    def __post_init__(self):
        if not self.message_id:
            self.message_id = f"msg-{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.trace_id:
            self.trace_id = f"trace-{uuid.uuid4().hex[:8]}"


class A2AProtocol:
    """
    Agent-to-Agent communication bus.
    Routes messages between agents with priority, deadlines, and tracing.
    """
    def __init__(self):
        self._agents: dict[str, Callable] = {}  # agent_id -> handler
        self._message_log: list[A2AMessage] = []
        self._pending_acks: dict[str, asyncio.Event] = {}
        self._stats = defaultdict(int)

    def register_agent(self, agent_id: str, handler: Callable):
        """Register an agent's message handler."""
        self._agents[agent_id] = handler
        logger.info("A2A: Registered agent '%s'", agent_id)

    def unregister_agent(self, agent_id: str):
        self._agents.pop(agent_id, None)
        logger.info("A2A: Unregistered agent '%s'", agent_id)

    async def send(self, message: A2AMessage) -> dict | None:
        """Send a message to an agent. Returns response if request."""
        self._message_log.append(message)
        self._stats[f"sent_{message.message_type}"] += 1
        if len(self._message_log) > 10000:
            self._message_log = self._message_log[-5000:]

        if message.to_agent == "all":
            # Broadcast to all agents
            responses = []
            for agent_id, handler in self._agents.items():
                if agent_id == message.from_agent:
                    continue
                try:
                    resp = await handler(message)
                    if resp:
                        responses.append({"agent": agent_id, "response": resp})
                except Exception as e:
                    logger.error("A2A broadcast to '%s' failed: %s", agent_id, e)
            return {"broadcast_responses": responses}

        target = message.to_agent
        if target not in self._agents:
            logger.warning("A2A: Agent '%s' not registered", target)
            return {"error": f"Agent '{target}' not registered"}

        handler = self._agents[target]
        try:
            self._stats[f"delivered_{message.message_type}"] += 1
            response = await handler(message)
            self._stats["successful_deliveries"] += 1
            return response
        except asyncio.TimeoutError:
            self._stats["timeouts"] += 1
            logger.error("A2A: Timeout sending to '%s' (deadline: %.0f)", target, message.deadline)
            return {"error": "timeout"}
        except Exception as e:
            self._stats["delivery_failures"] += 1
            logger.error("A2A: Delivery to '%s' failed: %s", target, e)
            return {"error": str(e)}

    async def request(self, from_agent: str, to_agent: str,
                      content: dict, priority: str = "normal",
                      timeout: float = 30.0) -> dict | None:
        """Send a task request and wait for response."""
        msg = A2AMessage(
            from_agent=from_agent, to_agent=to_agent,
            message_type="task_request",
            content=content, priority=priority,
            deadline=time.time() + timeout,
        )
        return await self.send(msg)

    async def query(self, from_agent: str, to_agent: str,
                    question: str, timeout: float = 15.0) -> dict | None:
        """Quick query between agents."""
        msg = A2AMessage(
            from_agent=from_agent, to_agent=to_agent,
            message_type="query",
            content={"question": question}, priority="normal",
            deadline=time.time() + timeout,
        )
        return await self.send(msg)

    def get_message_log(self, agent_id: str | None = None, limit: int = 50) -> list[dict]:
        """Get message log for debugging/audit."""
        logs = self._message_log
        if agent_id:
            logs = [m for m in logs if m.from_agent == agent_id or m.to_agent == agent_id]
        return [asdict(m) for m in logs[-limit:]]

    def stats(self) -> dict:
        return dict(self._stats)

a2a_protocol = A2AProtocol()
__all__ = ["A2AMessage", "A2AProtocol", "a2a_protocol"]
