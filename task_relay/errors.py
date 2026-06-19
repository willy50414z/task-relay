class TaskRelayError(RuntimeError):
    """Base task-relay error."""


class AgentNotFoundError(TaskRelayError):
    """Unknown or unsupported agent."""


class AgentExecutionError(TaskRelayError):
    """Agent subprocess or runtime failure."""


class AgentTimeoutError(AgentExecutionError):
    """Agent subprocess timed out."""


class AgentQuotaError(AgentExecutionError):
    """Agent failed due to quota or rate limiting."""


class OutcomeResolutionError(TaskRelayError):
    """Workspace outcome files could not be resolved."""


