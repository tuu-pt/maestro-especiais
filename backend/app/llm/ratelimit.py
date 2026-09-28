"""Pace of requests for the free quota (SPEC 6.1): per minute and per day, configurable.

acquire() waits for the next minute when the minute is full (the caller says "em fila") and
raises QuotaExhausted when the day is: generation stops and resumes later from the last block
done.
"""

import time
from collections.abc import Callable
from typing import Protocol


class QuotaExhausted(Exception):
    """The daily quota is used up."""


class RateLimiter(Protocol):
    def acquire(self, on_wait: Callable[[float], None] | None = None) -> None: ...


class MemoryRateLimiter:
    """In one process (tests)."""

    def __init__(self, rpm: int, rpd: int, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep) -> None:  # fmt: skip
        self.rpm, self.rpd, self.clock, self.sleep = rpm, rpd, clock, sleep
        self.minutes: dict[int, int] = {}
        self.days: dict[int, int] = {}

    def acquire(self, on_wait: Callable[[float], None] | None = None) -> None:
        while True:
            now = self.clock()
            day, minute = int(now // 86400), int(now // 60)
            if self.days.get(day, 0) >= self.rpd:
                raise QuotaExhausted("Quota diária do LLM esgotada: a geração retoma amanhã.")
            if self.minutes.get(minute, 0) < self.rpm:
                self.minutes[minute] = self.minutes.get(minute, 0) + 1
                self.days[day] = self.days.get(day, 0) + 1
                return
            wait = 60 - now % 60
            if on_wait:
                on_wait(wait)
            self.sleep(wait)


class RedisRateLimiter:
    """Shared by the API and the workers: counters with expiry in Redis."""

    def __init__(self, client: object, rpm: int, rpd: int, prefix: str = "llm",
                 clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep) -> None:  # fmt: skip
        self.client, self.rpm, self.rpd, self.prefix = client, rpm, rpd, prefix
        self.clock, self.sleep = clock, sleep

    def acquire(self, on_wait: Callable[[float], None] | None = None) -> None:
        redis = self.client
        while True:
            now = self.clock()
            day_key = f"{self.prefix}:day:{int(now // 86400)}"
            minute_key = f"{self.prefix}:minute:{int(now // 60)}"
            if int(redis.get(day_key) or 0) >= self.rpd:  # type: ignore[attr-defined]
                raise QuotaExhausted("Quota diária do LLM esgotada: a geração retoma amanhã.")
            count = redis.incr(minute_key)  # type: ignore[attr-defined]
            redis.expire(minute_key, 120)  # type: ignore[attr-defined]
            if count <= self.rpm:
                redis.incr(day_key)  # type: ignore[attr-defined]
                redis.expire(day_key, 2 * 86400)  # type: ignore[attr-defined]
                return
            wait = 60 - now % 60
            if on_wait:
                on_wait(wait)
            self.sleep(wait)
