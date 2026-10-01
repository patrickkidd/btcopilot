from sqlalchemy import Column, Enum, Float, Integer, Numeric, String, Text

from btcopilot.extensions import db
from btcopilot.modelmixin import ModelMixin
from btcopilot.models.qualityrun import Source

PARTS = ("people", "events", "pair_bonds", "clusters", "variables")


class ReplayPass(db.Model, ModelMixin):
    """One replay of a person's turns on one model, kept so a pass under the
    same case, prompt version, model and thinking level is never paid for
    twice [Oracle: R-0597]. `release` is null on passes kept before the table
    existed, whose release was not recorded; `scratch_diagram_id` is null when
    the pass ran on a copy of the database."""

    __tablename__ = "replay_passes"

    model = Column(String(64), nullable=False)
    thinking = Column(String(16), nullable=False)
    prompt = Column(String(16), nullable=False)
    case = Column(Text, nullable=True, index=True)
    turns = Column(Integer, nullable=False)
    calls = Column(Integer, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    cache_creation_tokens = Column(Integer, nullable=False)
    cache_read_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cost_usd = Column(Numeric(10, 6), nullable=False)
    people = Column(Float, nullable=True)
    events = Column(Float, nullable=True)
    pair_bonds = Column(Float, nullable=True)
    clusters = Column(Float, nullable=True)
    variables = Column(Float, nullable=True)
    overall = Column(Float, nullable=True)
    release = Column(String(64), nullable=True)
    source = Column(
        Enum(Source, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    scratch_diagram_id = Column(Integer, nullable=True)

    @property
    def key(self) -> str:
        return ReplayPass.key_of(self.case, self.prompt, self.model, self.thinking)

    @staticmethod
    def key_of(case: str, prompt: str, model: str, thinking: str) -> str:
        return f"{case} prompt {prompt} model {model} thinking {thinking}"

    @staticmethod
    def overall_of(scores: dict) -> float | None:
        """The mean of the parts that were scored."""
        scored = [scores[part] for part in PARTS if scores[part] is not None]
        return round(sum(scored) / len(scored), 2) if scored else None

    def __repr__(self):
        return f"<ReplayPass {self.id} {self.key}>"
