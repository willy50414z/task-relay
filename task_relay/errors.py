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


class DelegationOutputError(TaskRelayError):
    """A delegation's declared output artifact is missing or empty."""


class PacketGenerationError(TaskRelayError):
    """A delegation packet could not be generated (unknown mode or unresolvable read)."""


class ReviewGateConfigError(TaskRelayError):
    """Review gate configuration is invalid."""


class ReviewGateTimeoutError(TaskRelayError):
    """Review gate exceeded the configured global timeout."""


class ReviewArtifactError(TaskRelayError):
    """Review gate artifact verification failed."""




class DirtyWorkingTreeError(TaskRelayError):
    """Isolated delegation refused to run against a dirty main working tree."""
