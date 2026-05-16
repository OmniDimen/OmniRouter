import random
from dataclasses import dataclass, field


@dataclass
class PollingQueue:
    order: str = "sequential"
    items: list[int] = field(default_factory=list)
    pointer: int = 0
    _source: list[tuple[int, int]] = field(default_factory=list)

    def reset(self, model_weights: list[tuple[int, int]], order: str):
        self.order = order
        self._source = list(model_weights)
        self.items = []
        for model_id, weight in model_weights:
            self.items.extend([model_id] * weight)
        if self.order == "random":
            random.shuffle(self.items)
        self.pointer = 0

    def matches(self, model_weights: list[tuple[int, int]], order: str) -> bool:
        return self._source == list(model_weights) and self.order == order

    def next(self) -> int | None:
        if not self.items:
            return None
        if self.pointer >= len(self.items):
            if self.order == "random":
                random.shuffle(self.items)
            self.pointer = 0
        model_id = self.items[self.pointer]
        self.pointer += 1
        return model_id

    def consume_one(self, model_id: int):
        try:
            idx = self.items.index(model_id)
            self.items.pop(idx)
            if self.pointer > idx:
                self.pointer -= 1
            if self.pointer >= len(self.items):
                self.pointer = 0
        except ValueError:
            pass


class PollingManager:
    def __init__(self):
        self._queues: dict[int, PollingQueue] = {}

    def get_or_create(self, group_id: int) -> PollingQueue:
        if group_id not in self._queues:
            self._queues[group_id] = PollingQueue()
        return self._queues[group_id]

    def ensure_queue(
        self,
        group_id: int,
        model_weights: list[tuple[int, int]],
        order: str = "sequential",
    ):
        queue = self.get_or_create(group_id)
        if not queue.items or not queue.matches(model_weights, order):
            queue.reset(model_weights, order)

    def next_model(self, group_id: int) -> int | None:
        queue = self.get_or_create(group_id)
        return queue.next()

    def consume(self, group_id: int, model_id: int):
        queue = self.get_or_create(group_id)
        queue.consume_one(model_id)

    def invalidate(self, group_id: int):
        self._queues.pop(group_id, None)


polling_manager = PollingManager()
