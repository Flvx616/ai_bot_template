import re

from langchain_core.prompts import ChatPromptTemplate

from ..states import AgentState, AgentStatus


class ThinkTwiceNodes:
    """Mixin providing self-reflection capabilities for the agent."""

    MAX_LOOP_GENERATION = 3

    async def check_user_answer(self, state: AgentState) -> AgentState:
        """Check whether the original question (text) is covered in final_answer.

        Args:
            state: Current agent state.

        Returns:
            Dict with updated status and counter_loop.
            - status=DONE if final_answer is relevant to text.
            - status=AGAIN + counter_loop +=1 if not (max MAX_LOOP_GENERATION times).
        """
        prompt = self.langfuse_client.get_prompt("check_user_answer").get_langchain_prompt()
        prompt = ChatPromptTemplate.from_template(prompt)
        chain = prompt | self.llm
        response = await chain.ainvoke(
            {
                "question": state["text"],
                "parts": state.get("parts", "[]"),
                "history_questions": state.get("user_history", "[]"),
                "answer": state["final_answer"],
            }
        )
        response = "DONE" in response.content.strip().upper()

        if response:
            state["status"] = AgentStatus.DONE
            state["counter_loop"] = 0
            state["additional_info"] = ""
        else:
            counter = state.get("counter_loop", 0)
            if counter >= self.MAX_LOOP_GENERATION:
                state["status"] = AgentStatus.DONE
                state["counter_loop"] = 0
                state["additional_info"] = ""
            else:
                if not state.get("counter_loop"):
                    state["counter_loop"] = 0

                state["counter_loop"] += 1
                state["additional_info"] = state["final_answer"]
                state["status"] = AgentStatus.AGAIN
        return state

    async def generate_additional_questions(self, state) -> AgentState:
        """Generate new sub-questions to better answer the user's original question.

        Note:
            If the current answer is insufficient, the LLM generates new sub-questions
            which are then fed back into the answer_parts_async node.

        Return:
            Updated list of sub-questions (parts).
        """
        prompt = self.langfuse_client.get_prompt("generate_additional_questions").get_langchain_prompt()
        prompt = ChatPromptTemplate.from_template(prompt)
        chain = prompt | self.llm
        response = await chain.ainvoke(
            {
                "question": state["text"],
                "history_questions": state.get("user_history", "[]"),
                "answer": state["final_answer"],
                "parts": state.get("parts", "[]"),
            }
        )

        response = response.content.strip()

        content = re.search(r"<ЗАДАЧИ.*?>(.*?)</ЗАДАЧИ>", response, re.IGNORECASE | re.DOTALL)
        content = content.group(1) if content else response

        data = {"parts": [p.strip() for p in content.split("<PART>") if p.strip()]}
        return data
