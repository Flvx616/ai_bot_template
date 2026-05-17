import asyncio
import re
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from agents.rag_agent.states import AgentState
from service.logger import LoggerConfigurator

from .base import BaseAgentNodes
from .loop import ThinkTwiceNodes


class RagAgent(BaseAgentNodes, ThinkTwiceNodes):
    r"""RAG-based LangGraph agent.

    Note:
        1. Answers questions using a knowledge base (ChromaDB + RAG);
        2. Can rewrite and decompose complex questions;
        3. Caches intermediate results via Redis semantic cache.

    Customization:
        - Replace Langfuse prompt names to match your project's prompts.
        - Change COLLECTION_NAME to point at your ChromaDB collection.
    """

    def __init__(self, logger: LoggerConfigurator, llms: dict, cache, langfuse_client, chroma_client, **kwargs):
        self.logger = logger
        self.logger.info(f"Initializing {__name__}")
        self.llm = llms.get("default")
        self.logger.info(f"LLM keys: {list(llms.keys())}")

        self.cache = cache
        self.langfuse_client = langfuse_client
        self.chroma_client = chroma_client

        self.HISTORY_LIMIT = kwargs.get("HISTORY_LIMIT", 10)
        self.COLLECTION_NAME = kwargs.get("COLLECTION_NAME", "PRODUCTION_COLLECTION")

        self.logger.info(f"HISTORY_LIMIT: {self.HISTORY_LIMIT}")
        self.logger.info(f"COLLECTION_NAME: {self.COLLECTION_NAME}")

    async def _detect_topics_for_question(self, question: str) -> str:
        """Detect the topic category for a given question.

        Args:
            question: A single simple sub-question.

        Returns:
            The detected topic string.
        """
        prompt = self.langfuse_client.get_prompt("topic_choose_router").get_langchain_prompt()
        prompt = ChatPromptTemplate.from_template(prompt)
        chain = prompt | self.llm
        response = await chain.ainvoke({"question": question})
        return response.content.strip()

    async def decompose_question(self, state: AgentState) -> None | dict[str, Any] | dict[str, list[Any]]:
        """Decompose the user's complex question into a list of simple sub-questions.

        Note:
            1. A complex question is split into multiple simple ones to improve answer quality.
            2. Results are cached per user to avoid redundant LLM calls.

        Example:
            Input:  "Hello! Can you tell me how to get started and what I need to bring?"
            Output: ["How to get started?", "What do I need to bring?"]

        Return:
            Dict with a list of simple sub-questions under the key "parts".
        """
        question = state["text"]
        try:
            cached_result = self.cache.get(meta_info="decompose_question_" + state["user_id"], query=question)
            if cached_result:
                return {"parts": cached_result.get("json").get("parts")}
            else:
                prompt = self.langfuse_client.get_prompt("decompose_question").get_langchain_prompt()
                prompt = ChatPromptTemplate.from_template(prompt)
                chain = prompt | self.llm
                response = await chain.ainvoke(
                    {"user_question": question, "user_history": state.get("user_history", "")}
                )
                response = response.content.strip()

                content = re.search(r"<ЗАДАЧИ.*?>(.*?)</ЗАДАЧИ>", response, re.IGNORECASE | re.DOTALL)
                content = content.group(1) if content else response

                cache_data = {"parts": [p.strip() for p in content.split("<PART>") if p.strip()]}
                self.cache.save(
                    meta_info="decompose_question_" + state["user_id"], query=question, output="", json_data=cache_data
                )
                return cache_data
        except Exception as e:
            print(f"Error at decompose_question: {e}")

    async def answer_parts_async(self, state: AgentState, max_concurrent: int = 8) -> AgentState:
        """Generate answers to each sub-question asynchronously.

        Note:
            Uses a semaphore to limit concurrent LLM calls.
            Each sub-question gets its own RAG retrieval + LLM generation.

        Returns:
            State with a list of partial answers.
        """
        state["answers"] = []
        semaphore = asyncio.Semaphore(max_concurrent)

        prompt = self.langfuse_client.get_prompt("query_worker").get_langchain_prompt()
        prompt = ChatPromptTemplate.from_template(prompt)
        chain = prompt | self.llm

        async def call_llm(part: str) -> str:
            self.logger.info(f"Processing sub-question: {part}")
            async with semaphore:
                cached_result = self.cache.get(meta_info="answer_parts_async", query=part)
                if cached_result:
                    return cached_result.get("json").get("answer")
                else:
                    topic = await self._detect_topics_for_question(part)
                    self.logger.info(f"Detected topic: {topic}")
                    retrieved_data = await asyncio.to_thread(
                        self.chroma_client.get_info, query=part, collection_name=self.COLLECTION_NAME, topics=[topic]
                    )
                    html_data = retrieved_data.to_html()
                    result = await chain.ainvoke({"text": part, "rag": html_data})
                    cache_data = {"answer": result.content.strip()}
                    self.cache.save(meta_info="answer_parts_async", query=part, output="", json_data=cache_data)
                    return cache_data.get("answer")

        if state.get("parts"):
            tasks = [asyncio.create_task(call_llm(part)) for part in state["parts"]]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            state["answers"] = [str(r) if not isinstance(r, Exception) else f"Error: {r}" for r in results]
        return state

    async def collect_final_answer(self, state: AgentState) -> AgentState:
        """Assemble the final answer from all partial answers.

        Note:
            Takes into account:
            1. User's conversation history;
            2. Partial answers from sub-questions;
            3. The original user question.

        Return:
            Final text answer to the user's question.
        """
        question = state["text"]
        if state.get("answers"):
            answers_text = "\n".join(f"{i + 1}. {ans}" for i, ans in enumerate(state["answers"]) if ans)
            prompt = self.langfuse_client.get_prompt("summary_response").get_langchain_prompt()
            prompt = ChatPromptTemplate.from_template(prompt)
            chain = prompt | self.llm
            response = await chain.ainvoke(
                {
                    "task_responses": answers_text,
                    "user_history": state.get("user_history", "No conversation history."),
                    "original_question": question,
                    "model_answers": state.get("model_answers", "No previous model answers."),
                    "additional_info": state.get("additional_info", "No additional context from previous attempts."),
                }
            )
            response = response.content.strip()
            state["final_answer"] = response
        else:
            state["final_answer"] = "No data available to generate a final answer."
        return state
