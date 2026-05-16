from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class ModelState:
    fail_count: int = 0
    disabled: bool = False
    disabled_at: datetime | None = None
    disabled_until: datetime | None = None


class CircuitBreaker:
    def __init__(self):
        self._states: dict[int, ModelState] = {}

    def get_state(self, model_id: int) -> ModelState:
        if model_id not in self._states:
            self._states[model_id] = ModelState()
        return self._states[model_id]

    def is_available(self, model_id: int) -> bool:
        state = self.get_state(model_id)
        if not state.disabled:
            return True
        now = datetime.now(timezone.utc)
        if state.disabled_until and now >= state.disabled_until:
            state.disabled = False
            state.fail_count = 0
            state.disabled_at = None
            state.disabled_until = None
            return True
        return False

    def record_success(self, model_id: int):
        state = self.get_state(model_id)
        state.fail_count = 0

    def record_failure(self, model_id: int, threshold: int, duration_min: int) -> bool:
        """Returns True if the model just got disabled."""
        state = self.get_state(model_id)
        state.fail_count += 1
        if state.fail_count >= threshold and not state.disabled:
            now = datetime.now(timezone.utc)
            state.disabled = True
            state.disabled_at = now
            state.disabled_until = now + timedelta(minutes=duration_min)
            return True
        return False


breaker = CircuitBreaker()
