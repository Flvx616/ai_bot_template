from importlib.metadata import distribution

from fastapi import APIRouter, status

from . import schemas

router = APIRouter()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    response_model=schemas.HealthResponse,
)
async def health():
    from service.context import APP_CTX

    ctx = APP_CTX
    services = {
        "postgres": ctx._postgres_ext.health_check() if ctx._postgres_ext else False,
        "redis": ctx._redis_ext.health_check() if ctx._redis_ext else False,
        "chromadb": ctx._chroma_client.health_check() if ctx._chroma_client else False,
        "langfuse": ctx._langfuse_client.health_check() if ctx._langfuse_client else False,
    }
    svc_status = "ok" if all(services.values()) else "degraded"
    return schemas.HealthResponse(status=svc_status, services=services)


@router.get(
    "/info",
    status_code=status.HTTP_200_OK,
    response_model=schemas.InfoResponse,
)
async def info():
    dist = distribution("RagChatBot")

    return schemas.InfoResponse(
        name=str(dist.metadata["Name"]),
        description=str(dist.metadata["Description"]),
        type="REST API",
        version=str(dist.version),
    )
