"""The cluster F1 suite's table, one line per case, printed at the end of the run."""

import pytest

BOARD = pytest.StashKey[list[str]]()
HEADER = (
    f"{'case':18}{'want':>5}{'got':>5}{'paired':>7}"
    f"{'P':>6}{'R':>6}{'F1':>6}{'events F1':>10}{'openings':>9}{'refused':>8}{'voice':>6}{'cause':>6}  result"
)


@pytest.fixture
def board(request) -> list[str]:
    return request.config.stash.setdefault(BOARD, [])


def pytest_terminal_summary(terminalreporter, config):
    lines = config.stash.get(BOARD, [])
    if lines:
        terminalreporter.write_sep("-", "cluster F1")
        for line in [HEADER, *lines]:
            terminalreporter.write_line(line)
