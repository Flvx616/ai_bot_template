from langfuse import Langfuse
from langfuse.callback import CallbackHandler

from service.config import LangFuseSettings
from service.logger import LoggerConfigurator


class LangfuseClient:
    def __init__(self, app_config: LangFuseSettings, logger: LoggerConfigurator):
        self.config = app_config
        self.logger = logger

        self.logger.debug("Init LangfuseClient")
        self.logger.debug(f"Host: {self.config.host}")
        self.logger.debug(f"Secret Key: {self.config.secret_key[:4]}**{self.config.secret_key[-4:]}")
        self.logger.debug(f"Public Key: {self.config.public_key[:4]}**{self.config.public_key[-4:]}")
        self.logger.debug(f"Stage: {self.config.stage}")

        self.client = self.__create_client
        self.handler = self.__create_callback_handler

        self.logger.debug("LangFuse client created")

    @property
    def __create_client(self) -> Langfuse:
        """Create the Langfuse client object."""
        self.logger.debug("Creating Langfuse client")
        return Langfuse(
            secret_key=self.config.secret_key,
            public_key=self.config.public_key,
            host=self.config.host,
        )

    @property
    def __create_callback_handler(self) -> CallbackHandler:
        """Create the LangChain callback handler for LangGraph tracing."""
        return CallbackHandler(
            public_key=self.config.public_key,
            secret_key=self.config.secret_key,
            host=self.config.host,
            trace_name=self.config.stage,
        )

    async def on_startup(self) -> None:
        """Initialize the Langfuse client on application startup."""
        self.logger.info("LangFuse startup")
        try:
            self.client = self.__create_client
            self.handler = self.__create_callback_handler
            self.health_check()
        except Exception as e:
            Warning(f"LangFuse startup failed: {e}")

    def health_check(self) -> bool:
        """Check that Langfuse credentials are valid and the host is reachable.

        Return:
            True if connection is healthy.
        """
        is_healthy = self.client.auth_check()
        if not is_healthy:
            Warning("LangFuse Health check failed")
        return is_healthy
