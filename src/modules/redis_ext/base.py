import json
import os
from typing import Any, Dict, Optional

from langchain_community.embeddings.yandex import YandexGPTEmbeddings
from langchain_core.outputs import Generation
from langchain_redis import RedisSemanticCache

from service.logger import LoggerConfigurator


class RedisAdapter:
    def __init__(
        self,
        logger: LoggerConfigurator,
        embeddings: YandexGPTEmbeddings,
        redis_url: Optional[str],
        redis_threshold: Optional[float],
        redis_ttl: Optional[int],
    ) -> None:
        """Initialize the semantic cache backed by Redis.

        Args:
            logger: Logger instance.
            embeddings: Embedding model for semantic similarity.
            redis_url: Redis connection URL (e.g. "redis://localhost:6379").
            redis_threshold: Cosine distance threshold for cache hits (lower = stricter).
            redis_ttl: TTL for cached entries in seconds.
        """
        self.logger = logger
        self.redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379") if redis_url is None else redis_url
        self.redis_threshold = float(os.getenv("REDIS_THRESHOLD", 0.05)) if redis_threshold is None else redis_threshold
        self.redis_ttl = int(os.getenv("REDIS_TTL", 3600)) if redis_ttl is None else redis_ttl
        self.logger.info(f"Redis url: {self.redis_url}")
        self.embeddings = embeddings
        self.semantic_cache = RedisSemanticCache(
            redis_url=self.redis_url,
            embeddings=embeddings,
            distance_threshold=self.redis_threshold,
            ttl=self.redis_ttl,
        )
        self.logger.info(f"REDIS_THRESHOLD: {self.redis_threshold}")
        self.logger.info(f"REDIS_TTL: {self.redis_ttl}")

    def save(self, meta_info: str, query: str = "", output: str = "", json_data: Optional[dict] = None):
        """Save a result to the semantic cache.

        Args:
            meta_info: Cache namespace (e.g. "decompose_question_user123").
            query: The input query string used as the cache key.
            output: Optional plain text output.
            json_data: Optional structured data stored as JSON metadata.
        """
        metadata = {"json": json_data} if json_data else {}
        metadata["query"] = query
        metadata["output"] = output

        json_str = json.dumps(metadata)

        result = [Generation(text=json_str)]
        self.semantic_cache.update(query, meta_info, result)

    def get(self, meta_info: str, query: str = "") -> Optional[Dict[str, Any]]:
        """Look up a result from the semantic cache.

        Returns:
            The cached dict if a hit is found, otherwise None.
        """
        result = self.semantic_cache.lookup(query, meta_info)
        if result:
            try:
                return json.loads(result[0].text)
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
                return None
        return None

    def health_check(self) -> bool:
        """Simple health check."""
        return True if self.semantic_cache else False
