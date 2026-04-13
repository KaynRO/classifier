import os, time, redis
from typing import Optional
from helpers.logger import Logger


# Cross-worker rate limiter backed by Redis. Uses a sorted-set sliding window so
# multiple Celery workers (and multiple in-process threads) share the same quota.
# Each acquired slot is recorded with its timestamp; expired slots are pruned on
# every call. If the quota is full, wait until the oldest recorded slot falls
# out of the window, then retry.


_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        _redis_client = redis.from_url(url, decode_responses=True)
    return _redis_client


def rate_limit_wait(
    key: str,
    max_calls: int,
    window_seconds: int,
    logger: Optional[Logger] = None,
    max_wait_seconds: int = 300,
) -> None:
    # Acquire one slot of the named quota, blocking until one is available.
    # key: unique limiter name (e.g. "virustotal")
    # max_calls: quota size within the window (e.g. 4)
    # window_seconds: window length in seconds (e.g. 60)
    # max_wait_seconds: safety cap — if the limiter can't be acquired within
    #   this many seconds, just proceed and let the vendor API handle the rate
    #   error itself. Prevents runaway sleep loops.
    r = get_redis()
    rl_key = f"ratelimit:{key}"
    deadline = time.time() + max_wait_seconds

    while time.time() < deadline:
        now = time.time()
        cutoff = now - window_seconds

        pipe = r.pipeline()
        pipe.zremrangebyscore(rl_key, 0, cutoff)
        pipe.zcard(rl_key)
        _, count = pipe.execute()

        if count < max_calls:
            # Acquire a slot. Use a unique member so concurrent callers don't
            # stomp each other; Redis ZSET dedupes by member value.
            member = f"{now}:{os.getpid()}:{time.monotonic_ns()}"
            r.zadd(rl_key, {member: now})
            r.expire(rl_key, window_seconds + 5)
            return

        oldest = r.zrange(rl_key, 0, 0, withscores=True)
        if not oldest:
            continue
        oldest_ts = oldest[0][1]
        wait_for = max(0.25, (oldest_ts + window_seconds) - now + 0.1)
        if logger:
            logger.info(f"[*] {key} rate limit: {count}/{max_calls} in last {window_seconds}s, sleeping {wait_for:.1f}s")
        time.sleep(min(wait_for, 5.0))

    if logger:
        logger.warning(f"[!] {key} rate limit wait exceeded {max_wait_seconds}s, proceeding anyway")
