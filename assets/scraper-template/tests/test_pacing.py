from jemscrape.pacing import Pacer


class Recorder:
    def __init__(self):
        self.slept = []

    def __call__(self, seconds):
        self.slept.append(seconds)


def test_delay_never_below_floor():
    rec = Recorder()
    # rng always returns 0.1 (below floor); floor must win
    pacer = Pacer(min_delay=0.1, max_delay=0.1, floor=2.5,
                  rng=lambda a, b: 0.1, randint=lambda a, b: 999, sleep=rec)
    delay = pacer.wait()
    assert delay == 2.5
    assert rec.slept == [2.5]


def test_heavy_multiplies():
    pacer = Pacer(min_delay=10, max_delay=10, floor=1,
                  rng=lambda a, b: 10, randint=lambda a, b: 999, sleep=lambda s: None)
    assert pacer.wait(heavy=True) == 14.0


def test_coffee_break_adds_time_on_interval():
    # randint returns 1 → coffee break triggers on the 1st call; rng returns lo each call.
    seq = iter([5.0, 120.0])  # first rng() = base delay, second rng() = coffee break add

    def rng(a, b):
        return next(seq)

    pacer = Pacer(min_delay=5, max_delay=5, floor=1,
                  rng=rng, randint=lambda a, b: 1, sleep=lambda s: None)
    delay = pacer.wait()
    assert delay == 125.0  # 5 base + 120 coffee break
