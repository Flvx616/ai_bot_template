"""
Pydantic models for v1 API request/response bodies, errors, etc.
"""

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Standard user input schema.

    Customize fields here to match your bot's domain.
    The optional `context` field is prepended to `text` before sending to the agent,
    allowing callers to attach contextual metadata (e.g. department, product, locale).
    """

    text: str = Field(
        ...,
        min_length=4,
        max_length=512,
        examples=["What are the available options?"],
    )
    context: str = Field(
        default="",
        max_length=256,
        examples=["ProjectAlpha"],
        description="Optional context prefix (e.g. project name, department). Leave empty if not needed.",
    )

    class Config:
        extra = "forbid"


class AgentChatResponse(BaseModel):
    """Standard response schema."""

    response: str = Field(
        ..., min_length=1, max_length=4096, examples=["Here is the answer to your question..."]
    )

    class Config:
        extra = "forbid"


class FailedDependecyResponse(BaseModel):
    error_description: str = Field(
        description="Description of the error.", examples=["YandexGPT service temporarily unavailable."]
    )


class LLMAPITestResponse(BaseModel):
    """Response for /test_invoke route."""

    answer: str = Field(description="LLM response to the test question")


class LLMAPITestRequest(BaseModel):
    question: str = Field(
        description="Test question for the LLM", min_length=4, max_length=500, examples=["Who are you?"]
    )

    generation_params: dict | None = Field(
        description="Optional generation parameters.",
        default={},
        examples=[
            {
                "model": "yandexgpt",
                "temperature": 0.32,
                "max_tokens": 2048,
            }
        ],
    )
