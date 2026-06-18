from typing import Protocol

from task_relay.types import AgentRunRequest, AgentRunResult, TargetStatus


class AgentRunner(Protocol):
    name: str

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        ...

    def check(self) -> TargetStatus:
        ...
