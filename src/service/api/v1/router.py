"""
v1 API endpoints.
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from langchain_openai import ChatOpenAI

from agents.rag_agent import AgentStatus, build_builder
from service.config import APP_CONFIG
from service.context import APP_CTX

from . import schemas
from .schemas import AgentChatRequest, AgentChatResponse, FailedDependecyResponse, LLMAPITestResponse
from .utils import common_headers

router = APIRouter()
logger = APP_CTX.get_logger()


@router.post(
    "/test_invoke",
    status_code=status.HTTP_200_OK,
    response_model=LLMAPITestResponse,
    responses={
        status.HTTP_424_FAILED_DEPENDENCY: {
            "description": "LLM API call failed",
            "model": schemas.FailedDependecyResponse,
        },
    },
)
async def llm_test(
    request: schemas.LLMAPITestRequest,
    headers: dict = Depends(common_headers),
    yandexgpt_base_params=Depends(APP_CTX.get_yandexgpt_base_params),
):
    """Simple LLM connectivity test — sends a question directly to YandexGPT."""
    llm_client = ChatOpenAI(**yandexgpt_base_params)
    logger.debug(f"Testing LLM for user {headers.get('x-user-id')}")
    try:
        answer = llm_client.invoke(request.question)
        logger.debug(f"LLM answer: {answer}")
    except Exception as e:
        logger.error(f"LLM test failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            content=FailedDependecyResponse(error_description=str(e)).model_dump(),
        )
    return LLMAPITestResponse(answer=answer.content)


@router.post("/chat", status_code=status.HTTP_200_OK, response_model=AgentChatResponse)
async def chat(
    request: AgentChatRequest,
    headers: dict = Depends(common_headers),
):
    """Main chat endpoint — invokes the RAG agent graph.

    Args:
        request: User's message with optional context prefix.
        headers: System headers (trace-id, user-id, etc.).
    """
    rate_limiter = await APP_CTX.get_ratelimiter()
    allowed, current = rate_limiter.check_and_increment(user_id=headers.get("x-user-id"))

    if not allowed:
        ttl = rate_limiter.ttl(user_id=headers.get("x-user-id"))
        return AgentChatResponse(
            response=f"You have exceeded your request limit. Please try again in {ttl} seconds."
        )

    logger.debug(f"Input text length: {len(request.text)}")

    # Prepend context prefix to the text if provided
    full_text = f"{request.context} | {request.text}" if request.context else request.text

    agent_payload = {
        "user_id": headers.get("x-user-id"),
        "text": full_text,
        "status": AgentStatus.ACTIVE,
    }
    try:
        client = await APP_CTX.get_postgres_client()
        async with client.get_user_checkpointer() as checkpointer:
            agent_graph = build_builder(agent=APP_CTX.get_agent(), checkpointer=checkpointer)

            langfuse = await APP_CTX.get_langfuse()

            config = {
                "configurable": {"thread_id": headers.get("x-user-id")},
                "callbacks": [langfuse.handler],
                "metadata": {
                    "stage": APP_CONFIG.app.stage,
                    "langfuse_session_id": headers.get("x-trace-id"),
                    "langfuse_user_id": headers.get("x-user-id"),
                },
            }

            result = await agent_graph.ainvoke(
                input=agent_payload,
                config=config,
            )
            logger.debug(f"Answer generated. Length: {len(result['final_answer'])} chars")
        return AgentChatResponse(response=result["final_answer"])

    except Exception as e:
        logger.critical(
            f"Agent error: "
            f"[user_id={headers.get('x-user-id')}], "
            f"[session_id={headers.get('x-trace-id')}], "
            f"[source={headers.get('x-source-id')}] "
            f"{e}"
        )
        return AgentChatResponse(response="An internal error occurred. Please try again later.")
