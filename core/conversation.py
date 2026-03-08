"""
Conversation turn management and state machine.
Tracks speaker turns, intent, and slot state within a session.
"""

from dataclasses import dataclass, field
from enum import Enum


class AgentState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


@dataclass
class Turn:
    role: str          # "user" or "assistant"
    content: str
    timestamp: float


@dataclass
class ConversationContext:
    session_id: str
    state: AgentState = AgentState.IDLE
    turns: list[Turn] = field(default_factory=list)
    intent: str | None = None
    slots: dict = field(default_factory=dict)

    def add_turn(self, role: str, content: str, timestamp: float):
        self.turns.append(Turn(role=role, content=content, timestamp=timestamp))

    def to_messages(self) -> list[dict]:
        """Convert turns to OpenAI-compatible message list."""
        return [{"role": t.role, "content": t.content} for t in self.turns]
