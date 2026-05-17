from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response for /health endpoint."""

    status: str = Field(description="Overall health: 'ok' or 'degraded'", max_length=10)
    services: dict[str, bool] = Field(
        default_factory=dict,
        description="Per-service health status (True = initialized, False = not ready)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "services": {"postgres": True, "redis": True, "chromadb": True, "langfuse": True},
            }
        }


class InfoResponse(BaseModel):
    """Response for /info endpoint."""

    name: str = Field(description="Service name", max_length=50)
    description: str = Field(description="Service description", max_length=200)
    type: str = Field(default="REST API", description="Service type", max_length=20)
    version: str = Field(description="Service version", max_length=20, pattern=r"^\d+.\d+.\d+")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "rag-chatbot-template",
                "description": "LangGraph RAG agent template",
                "type": "REST API",
                "version": "0.1.0",
            }
        }


class RateResponse(BaseModel):
    rating_result: str = Field(description="Rating that was recorded", max_length=50)
