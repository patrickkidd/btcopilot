"""What each live case must do to pass: once, a check on the record after one
turn; or k of n, the case run n times on a fresh session and passing when at
least k of those runs do."""

import functools
from dataclasses import dataclass

import pytest

WAITING = (
    "coding rule undecided; awaits ratified ground truth from the IRR review group"
)
waiting = pytest.mark.waiting


@dataclass(frozen=True)
class Criterion:
    k: int
    n: int

    def __str__(self) -> str:
        return "once" if self.n == 1 else f"{self.k} of {self.n}"


def missed(case, args, kwargs) -> str | None:
    try:
        case(*args, **kwargs)
    except AssertionError as miss:
        return str(miss)
    return None


def passes(k: int, of: int):
    criterion = Criterion(k, of)

    def declare(case):
        if of == 1:
            case.criterion = criterion
            return case

        @functools.wraps(case)
        def sampled(*args, **kwargs):
            misses = [
                m
                for m in (missed(case, args, kwargs) for _ in range(of))
                if m is not None
            ]
            assert (
                of - len(misses) >= k
            ), f"{of - len(misses)} of {of} runs passed, {k} needed: {misses}"

        sampled.criterion = criterion
        return sampled

    return declare


once = passes(1, of=1)
