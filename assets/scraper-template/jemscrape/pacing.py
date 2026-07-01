import random
import time


class Pacer:
    def __init__(self, min_delay, max_delay, floor,
                 rng=random.uniform, randint=random.randint, sleep=time.sleep):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.floor = floor
        self._rng = rng
        self._randint = randint
        self._sleep = sleep
        self._count = 0
        self._next_break_at = self._randint(20, 30)

    def wait(self, heavy=False):
        self._count += 1
        delay = self._rng(self.min_delay, self.max_delay)
        if heavy:
            delay *= 1.4
        if delay < self.floor:
            delay = self.floor
        if self._count >= self._next_break_at:
            delay += self._rng(90, 240)
            self._count = 0
            self._next_break_at = self._randint(20, 30)
        self._sleep(delay)
        return delay
