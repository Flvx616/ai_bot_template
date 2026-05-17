from typing import Tuple

import redis


class UserRateLimiter:
    """Limits the number of requests (messages) from a specific user_id
    within a fixed time window.

    Uses atomic Redis INCR + EXPIRE commands.
    """

    def __init__(self, logger, **kwargs):
        self.logger = logger
        self.logger.info("Create Redis UserRateLimiter")
        self.USER_QUERY_LIMIT_N = kwargs.get("USER_QUERY_LIMIT_N", 10)
        self.USER_QUERY_LIMIT_TTL_SECONDS = int(kwargs.get("USER_QUERY_LIMIT_TTL_SECONDS", 20 * 3600))
        self.RATE_LIMIT_TEMPLATE = kwargs.get("RATE_LIMIT_TEMPLATE", "msg_count:{user_id}")

        self.logger.info(f"Limit template: {self.RATE_LIMIT_TEMPLATE}")
        self.logger.info(f"Query limit: {self.USER_QUERY_LIMIT_N}")
        self.logger.info(f"Expire time: {self.USER_QUERY_LIMIT_TTL_SECONDS}")
        self.logger.info(f"Host: {kwargs.get('host', '127.0.0.1')}")
        self.logger.info(f"Port: {kwargs.get('port', 6379)}")

        self.redis = redis.Redis(
            host=kwargs.get("host", "127.0.0.1"),
            port=kwargs.get("port", 6379),
            db=kwargs.get("db", 2),
            decode_responses=kwargs.get("decode_responses", True),
        )
        self.logger.info("Redis UserRateLimiter has been initialized")

    def check_and_increment(self, user_id: str) -> Tuple[bool, int]:
        """Increment user counter and check if within limit.

        Args:
            user_id: Unique user identifier.

        Returns:
            Tuple (allowed, current_count) where allowed=True if under limit.
        """
        key = self.RATE_LIMIT_TEMPLATE.format(user_id=user_id)

        with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.ttl(key)
            results = pipe.execute()
            current, ttl = results

        if current == 1 or ttl == -1 or ttl == -2:
            self.redis.expire(key, self.USER_QUERY_LIMIT_TTL_SECONDS)

        allowed = current <= self.USER_QUERY_LIMIT_N
        return allowed, current

    def get_remaining(self, user_id: str) -> int:
        """Return the number of remaining allowed requests for this user."""
        key = self.RATE_LIMIT_TEMPLATE.format(user_id=user_id)
        value = self.redis.get(key)
        value = int(value) if value is not None else 0
        remaining = max(self.USER_QUERY_LIMIT_N - value, 0)
        return remaining

    def reset_counter(self, user_id: str) -> None:
        """Force-reset the request counter for a user (e.g. admin action)."""
        key = self.RATE_LIMIT_TEMPLATE.format(user_id=user_id)
        self.redis.delete(key)

    def ttl(self, user_id: str) -> int:
        """Return the remaining TTL for the user's rate limit key.

        Returns -2 if the key does not exist, -1 if it has no TTL.
        """
        key = self.RATE_LIMIT_TEMPLATE.format(user_id=user_id)
        return self.redis.ttl(key)

    def health_check(self) -> bool:
        """Ping Redis to verify connectivity."""
        pong = self.redis.ping()
        if not pong:
            self.logger.warning("Redis PING returned False")
            return False
        return True
