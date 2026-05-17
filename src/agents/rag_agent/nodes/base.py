from langchain_core.prompts import ChatPromptTemplate

from agents.rag_agent.states import AgentState


class BaseAgentNodes:
    async def validate_text(self, state: AgentState) -> AgentState:
        """Validate that the user's input complies with the content policy.

        Notes:
            1. Node for detecting spam or off-topic requests;
            2. Results are cached globally in Redis by question similarity.

        Return:
            Binary flag — valid or invalid request.
        """
        question = state["text"]
        try:
            cached_result = self.cache.get(meta_info="validate_input", query=question)
            if cached_result:
                self.logger.debug(f"Cached result {cached_result}")
                state["is_valid"] = cached_result.get("json").get("is_valid")
                state["final_answer"] = cached_result.get("json").get("final_answer")
                return state
            else:
                self.logger.debug(f"Cache miss for validate_input")
                prompt = ChatPromptTemplate.from_template(
                    self.langfuse_client.get_prompt("policy_validation").get_langchain_prompt()
                )
                chain = prompt | self.llm
                output = await chain.ainvoke({"text": state["text"]})
                output = output.content.strip().lower()
                self.logger.info(f"Validation output: {output}")

            is_valid = "да" in output

            cache_data = {"is_valid": is_valid}

            if not is_valid:
                cache_data["final_answer"] = "Request did not pass validation"
                state["final_answer"] = cache_data["final_answer"]

            state["is_valid"] = is_valid
            self.logger.debug(f"is_valid: {is_valid}")
            self.cache.save(meta_info="validate_input", query=question, output="", json_data=cache_data)
            return state

        except Exception as e:
            print(f"Error at validate_text: {e}")

    async def validate_final_answer(self, state: AgentState) -> AgentState:
        """Validate that the model's output complies with the content policy.

        Notes:
            1. Node for detecting policy violations in generated answers;
            2. Results are cached globally in Redis.

        Return:
            Binary flag — valid or invalid response.
        """
        final_answer = state.get("final_answer", "")
        try:
            cached_result = self.cache.get(meta_info="validate_final_answer", query=final_answer)
            if cached_result:
                state["is_valid"] = cached_result.get("json").get("is_valid") or True
                return state
            else:
                prompt = self.langfuse_client.get_prompt("policy_validation").get_langchain_prompt()
                prompt = ChatPromptTemplate.from_template(prompt)
                chain = prompt | self.llm
                output = await chain.ainvoke({"text": final_answer})

                is_valid = "да" in output.content.strip().lower()
                cache_data = {"answer": is_valid}
                if not is_valid:
                    state["final_answer"] = "Response did not pass validation"
                state["is_valid"] = is_valid
                self.cache.save(meta_info="validate_final_answer", query=final_answer, output="", json_data=cache_data)
                return state

        except Exception as e:
            print(f"Error at validate_final_answer: {e}")

    def update_user_history_context(self, state: AgentState) -> AgentState:
        """Update question/answer history: append current pair, trim to HISTORY_LIMIT.

        Args:
            state: Current state containing user_history, model_answers, text, final_answer.

        Returns:
            Updated state with synchronized history (last HISTORY_LIMIT question-answer pairs).
        """
        if state.get("user_history"):
            state["user_history"].append(state["text"])
        else:
            state["user_history"] = [state["text"]]

        if state.get("model_answers"):
            state["model_answers"].append(state.get("final_answer", ""))
        else:
            state["model_answers"] = [state["final_answer"]]

        if len(state["user_history"]) > self.HISTORY_LIMIT:
            trim_count = len(state["user_history"]) - self.HISTORY_LIMIT
            state["user_history"] = state["user_history"][-self.HISTORY_LIMIT :]
            state["model_answers"] = state["model_answers"][-trim_count:]

        return {"user_history": state["user_history"], "model_answers": state["model_answers"]}

    def reject_stub(self, state: AgentState) -> AgentState:
        """Fallback response when the agent fails to generate a valid answer."""
        state["final_answer"] = (
            "Your message does not match the expected topic for this assistant. "
            "Please rephrase your question and try again."
        )
        return state
