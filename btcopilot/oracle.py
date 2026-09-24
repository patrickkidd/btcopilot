"""The one reader of the rulings store (private/oracle, sops-encrypted).

Nothing else parses the store. Reading it needs a sops key in SOPS_AGE_KEY_FILE
or SOPS_AGE_KEY; without one it raises rather than reading as empty.
"""

import enum
import hashlib
import re
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from btcopilot.promptdir import key_present

ROOT = Path(__file__).parents[1]
STORE = ROOT / "private" / "oracle"
INDEX = STORE / "rulings.md"
EVIDENCE = STORE / "evidence.md"
FIELDS = ("id", "statement", "kind", "tags", "status", "evidence_count", "origin")
ROW = re.compile(r"^R-\d{4} \|")
ID = re.compile(r"R-\d{4}")
QUOTE = "> "


class Kind(enum.Enum):
    Rule = "rule"
    Journey = "journey"
    Defect = "defect"


class Status(enum.Enum):
    Ok = "OK"
    Gap = "GAP"
    Waived = "WAIVED"
    Superseded = "SUPERSEDED"
    TestOwed = "TEST OWED"
    Duplicate = "DUPLICATE"


POINTING = {Status.Superseded, Status.Duplicate}


class Tag(enum.Enum):
    Account = "account"
    Admin = "admin"
    Affordance = "affordance"
    Agents = "agents"
    Anxiety = "anxiety"
    Architecture = "architecture"
    Avatar = "avatar"
    Beta = "beta"
    Business = "business"
    Chalkboard = "chalkboard"
    Chat = "chat"
    Chips = "chips"
    Clusters = "clusters"
    Coach = "coach"
    Comms = "comms"
    Composer = "composer"
    Conflict = "conflict"
    Corpus = "corpus"
    Cost = "cost"
    Cutoff = "cutoff"
    DataModel = "data-model"
    DataNature = "data-nature"
    Database = "database"
    Defect = "defect"
    DefinedSelf = "defined-self"
    Deploy = "deploy"
    Design = "design"
    DesignProcess = "design-process"
    Distance = "distance"
    Dns = "dns"
    Drawability = "drawability"
    Drawing = "drawing"
    Editor = "editor"
    Evaluation = "evaluation"
    Events = "events"
    Extraction = "extraction"
    FamilyDiagram = "family-diagram"
    Fixtures = "fixtures"
    Functioning = "functioning"
    Fusion = "fusion"
    Identity = "identity"
    Import = "import"
    Irr = "irr"
    Layout = "layout"
    ListView = "list-view"
    Logging = "logging"
    Memory = "memory"
    Model = "model"
    Money = "money"
    Navigation = "navigation"
    Observability = "observability"
    Onboarding = "onboarding"
    Picture = "picture"
    Plan = "plan"
    Platform = "platform"
    PlayByPlay = "play-by-play"
    Privacy = "privacy"
    ProApp = "pro-app"
    Process = "process"
    ProductConcept = "product-concept"
    Projection = "projection"
    Prompts = "prompts"
    QuestionLanguage = "question-language"
    Record = "record"
    Recording = "recording"
    Release = "release"
    Repo = "repo"
    Review = "review"
    Roles = "roles"
    Sarf = "sarf"
    Scrolling = "scrolling"
    Security = "security"
    Sessions = "sessions"
    Settings = "settings"
    Shell = "shell"
    Symbols = "symbols"
    Symptom = "symptom"
    Testing = "testing"
    Timing = "timing"
    TitleRow = "title-row"
    Tokens = "tokens"
    Tooling = "tooling"
    Toward = "toward"
    Traceability = "traceability"
    Training = "training"
    Triangle = "triangle"
    UiStandards = "ui-standards"
    VisualLanguage = "visual-language"
    Voice = "voice"
    Wide = "wide"
    Words = "words"


@dataclass(frozen=True)
class Ruling:
    id: str
    statement: str
    kind: Kind
    tags: tuple[Tag, ...]
    status: Status
    pointer: tuple[str, ...]
    evidence_count: int
    origin: str


def decrypt(path: Path) -> str:
    if not key_present():
        raise RuntimeError(
            f"{path.relative_to(ROOT)} needs a sops key: set SOPS_AGE_KEY_FILE or SOPS_AGE_KEY"
        )
    done = subprocess.run(
        ["sops", "-d", str(path)], capture_output=True, text=True, check=True
    )
    return done.stdout


def status(field: str) -> tuple[Status, tuple[str, ...]]:
    word = next((s for s in Status if field == s.value or field.startswith(s.value + " ")), None)
    if word is None:
        raise ValueError(f"status {field!r} is not in the closed vocabulary")
    pointer = tuple(ID.findall(field[len(word.value) :]))
    if (word in POINTING) != bool(pointer):
        raise ValueError(f"status {field!r} must name a ruling exactly when it is {'/'.join(s.value for s in POINTING)}")
    return word, pointer


def ruling(row: str) -> Ruling:
    cols = [c.strip() for c in row.split(" | ")]
    if len(cols) != len(FIELDS):
        raise ValueError(f"{cols[0]} has {len(cols)} fields, not 7")
    rid, statement, kind, tags, stat, count, origin = cols
    if not re.fullmatch(r"R-\d{4}", rid) or not statement or not origin or not tags:
        raise ValueError(f"{rid} has an empty or malformed field")
    word, pointer = status(stat)
    return Ruling(
        id=rid,
        statement=statement,
        kind=Kind(kind),
        tags=tuple(Tag(t.strip()) for t in tags.split(",")),
        status=word,
        pointer=pointer,
        evidence_count=int(count),
        origin=origin,
    )


def parse(text: str) -> dict[str, Ruling]:
    found = {}
    for row in text.splitlines():
        if not ROW.match(row):
            continue
        r = ruling(row)
        if r.id in found:
            raise ValueError(f"{r.id} appears twice")
        found[r.id] = r
    for r in found.values():
        for other in r.pointer:
            if other not in found:
                raise ValueError(f"{r.id} points at {other}, which is not in the store")
    return found


@cache
def index() -> str:
    return decrypt(INDEX)


@cache
def rulings() -> dict[str, Ruling]:
    return parse(index())


def quoted(text: str) -> dict[str, list[str]]:
    """Each ruling's quotes. After a free-text header, a block is a line that is
    exactly the id, then its "> " quote lines, then a blank line."""
    out, current = {}, None
    for line in text.splitlines():
        if re.fullmatch(r"R-\d{4}", line):
            if line in out:
                raise ValueError(f"evidence for {line} appears twice")
            current = out[line] = []
        elif not line.strip():
            current = None
        elif current is not None:
            if not line.startswith(QUOTE):
                raise ValueError(f"evidence line under an id does not start with {QUOTE!r}: {line[:40]!r}")
            current.append(" ".join(line[len(QUOTE) :].split()))
    return out


@cache
def quotes() -> dict[str, list[str]]:
    return quoted(decrypt(EVIDENCE))


def fingerprints() -> dict[str, set[str]]:
    return {
        rid: {hashlib.sha256(q.encode()).hexdigest()[:16] for q in qs}
        for rid, qs in quotes().items()
    }


def pinned(text: str) -> dict[str, list[str]]:
    return {rid: digests for rid, *digests in (l.split() for l in text.splitlines() if l.strip())}


def pin(text: str) -> str:
    """The fingerprint file with new ids and new quotes appended; nothing already
    pinned is dropped or reordered. An id with no quotes yet is pinned bare."""
    old, now = pinned(text), fingerprints()
    rows = [[rid, *ds, *sorted(now.get(rid, set()) - set(ds))] for rid, ds in old.items()]
    rows += [[rid, *sorted(now.get(rid, set()))] for rid in sorted((set(rulings()) | set(now)) - set(old))]
    return "".join(" ".join(r) + "\n" for r in rows)
