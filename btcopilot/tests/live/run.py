"""One live run's spend and results. Every model call is charged at the app's
own prices as it is written down; a run stops at RUN_CAP, and every run on one
day together stop at DAILY_CAP. Each run leaves one results file."""

import datetime
import enum
import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path

import anthropic
import pytest

from btcopilot.coachmodel import Spent
from btcopilot.pricing import cost

RUN_CAP = Decimal("3.00")
DAILY_CAP = RUN_CAP
RESULTS = Path(__file__).parent / "results"


class Outcome(enum.StrEnum):
    Passed = "passed"
    Failed = "failed"
    Skipped = "skipped"


class Status(enum.StrEnum):
    Passed = "passed"
    Failed = "failed"
    Stopped = "stopped"


@dataclass
class Case:
    criterion: str
    outcome: Outcome | None = None
    spent: Spent = field(default_factory=Spent)
    cost: Decimal = Decimal(0)


def spent_of(usage) -> Spent:
    return Spent(
        input=usage.input_tokens,
        output=usage.output_tokens,
        cache_creation=usage.cache_creation_input_tokens or 0,
        cache_read=usage.cache_read_input_tokens or 0,
    )


class Run:
    def __init__(self, model: str, git: str, results: Path = RESULTS):
        self.model = model
        self.git = git
        self.results = results
        self.started = datetime.datetime.now(datetime.timezone.utc)
        self.spent = Spent()
        self.cost = Decimal(0)
        self.cases: dict[str, Case] = {}
        self.case: Case | None = None
        self.reason: str | None = None
        self.path: Path | None = None
        self.row: dict | None = None

    @property
    def day(self) -> str:
        return self.started.date().isoformat()

    @property
    def ledger(self) -> Path:
        return self.results / "daily.json"

    def days(self) -> dict[str, str]:
        return json.loads(self.ledger.read_text()) if self.ledger.exists() else {}

    def today(self) -> Decimal:
        return Decimal(self.days().get(self.day, "0"))

    def stop(self, reason: str) -> None:
        self.reason = self.reason or reason

    def open(self, key: str) -> None:
        """Before any spend: today's ledger is under its cap, and the API takes
        one 1-token call on the testing key. Otherwise the run stops here."""
        if self.today() >= DAILY_CAP:
            self.stop(f"today's cap of ${DAILY_CAP} is already spent")
        else:
            client = anthropic.Anthropic(api_key=key)
            try:
                message = client.messages.create(
                    model=self.model,
                    max_tokens=1,
                    messages=[{"role": "user", "content": "ok"}],
                )
            except anthropic.APIStatusError as refused:
                self.stop(f"the balance check was refused: {refused.message}")
            else:
                spent = spent_of(message.usage)
                self.charge(spent, cost(message.model, spent))
        if self.reason:
            pytest.exit(f"live run stopped: {self.reason}")

    def charge(self, spent: Spent, dollars: Decimal) -> None:
        self.spent.add(spent)
        self.cost += dollars
        if self.case:
            self.case.spent.add(spent)
            self.case.cost += dollars
        days = self.days()
        days[self.day] = str(self.today() + dollars)
        self.ledger.write_text(json.dumps(days, indent=2))
        if self.cost >= RUN_CAP:
            self.stop(f"the run cap of ${RUN_CAP} is reached")
        elif self.today() >= DAILY_CAP:
            self.stop(f"today's cap of ${DAILY_CAP} is reached")

    def recorded(self, mapper, connection, call) -> None:
        """A model call written down by the app, charged as it is written."""
        self.charge(
            Spent(
                input=call.input_tokens,
                output=call.output_tokens,
                cache_creation=call.cache_creation_tokens,
                cache_read=call.cache_read_tokens,
            ),
            call.cost_usd,
        )

    def begin(self, name: str, criterion: str) -> None:
        self.case = self.cases[name] = Case(criterion)

    def end(self, name: str, outcome: Outcome) -> None:
        self.cases[name].outcome = outcome

    def finish(self, exitstatus: int) -> dict:
        if exitstatus == pytest.ExitCode.INTERRUPTED:
            self.stop("interrupted")
        if self.reason:
            status = Status.Stopped
        elif exitstatus == pytest.ExitCode.OK:
            status = Status.Passed
        else:
            status = Status.Failed
        self.row = {
            "date": self.started.isoformat(timespec="seconds"),
            "model": self.model,
            "git": self.git,
            "status": status,
            "reason": self.reason,
            "tokens": asdict(self.spent),
            "cost": float(self.cost),
            "cases": [
                {
                    "case": name,
                    "criterion": case.criterion,
                    "outcome": case.outcome,
                    "tokens": asdict(case.spent),
                    "cost": float(case.cost),
                }
                for name, case in self.cases.items()
            ],
        }
        self.path = self.results / f"{self.started:%Y-%m-%dT%H%M%S}-{self.git[:8]}.json"
        self.path.write_text(json.dumps(self.row, indent=2))
        return self.row

    def summary(self) -> str:
        stopped = f" ({self.reason})" if self.reason else ""
        return (
            f"live run {self.row['status']}{stopped}: ${self.cost:.4f} spent "
            f"({self.spent.input} tokens in, {self.spent.output} out, "
            f"{self.spent.cache_creation} cached, {self.spent.cache_read} read back); "
            f"${self.today():.4f} of ${DAILY_CAP} spent today; results in {self.path}"
        )
