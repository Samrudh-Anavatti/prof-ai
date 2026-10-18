import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

MESSAGES_PER_MINUTE = 10
# A turn whose stream was never consumed (client gone) must not block the user forever.
IN_FLIGHT_EXPIRY_SECONDS = 120


class TurnLimiter:
    """Per-user rate limit and one reply in flight. In-process: assumes a single instance."""

    def __init__(
        self,
        per_minute: int = MESSAGES_PER_MINUTE,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._per_minute = per_minute
        self._clock = clock
        self._lock = threading.Lock()
        self._recent: dict[str, deque[float]] = defaultdict(deque)
        self._in_flight: dict[str, float] = {}

    def try_acquire(self, user_id: str) -> str | None:
        """Reserve a turn, or return why the user has to wait."""
        now = self._clock()
        with self._lock:
            started = self._in_flight.get(user_id)
            if started is not None and now - started < IN_FLIGHT_EXPIRY_SECONDS:
                return "Wait for the current reply to finish."
            recent = self._recent[user_id]
            while recent and now - recent[0] >= 60:
                recent.popleft()
            if len(recent) >= self._per_minute:
                return "You're sending messages too quickly. Wait a minute and try again."
            recent.append(now)
            self._in_flight[user_id] = now
            return None

    def release(self, user_id: str) -> None:
        with self._lock:
            self._in_flight.pop(user_id, None)
