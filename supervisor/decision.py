from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentDecision:
    name: str
    status: str
    reason: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SupervisorDecision:
    approved: bool
    action: str
    reason: str
    agents: list[AgentDecision]

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "action": self.action,
            "reason": self.reason,
            "agents": [asdict(agent) for agent in self.agents],
        }

