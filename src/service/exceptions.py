from fastapi import status


class AgentError(Exception):
    """Base exception for agent errors."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class AgentInternalError(AgentError):
    """Internal graph / logic bugs."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
