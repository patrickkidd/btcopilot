from dataclasses import dataclass


@dataclass
class Decision:
    item: str
    field: str
    before: str
    after: str
    reason: str
