"""FD-326 conversational quality evaluator.

Replaces eyeball review with an LLM-judge over the four dimensions that
emerged during FD-325/326 development. Returns per-conversation pass/fail
plus the offending turns, so a human verifies a table, not transcripts.

Dimensions (all judged against the user's actual turns, not a rubric):
- current_events_engagement: on opening / current-events turns the coach
  engages with what the user brought rather than pivoting to family-history
  intake or pitching theory.
- name_usage: when the coach references a family member already in the
  diagram it uses their name, not "your mother" / "your sister".
- no_premature_pivot: the coach does not abandon a live topic the user is
  still working through to jump to unrelated intake.
- no_theory_pitch: the coach does not deliver "why family systems matters"
  preambles or therapy clichés ("it sounds like", "I'm so sorry to hear").
"""
import json
import re
from dataclasses import dataclass

from btcopilot.llmutil import gemini_text_sync

_BOOL_KEYS = (
    "current_events_engagement", "name_usage", "no_premature_pivot",
    "no_theory_pitch", "returns_to_collection",
)


def _parse_judge(raw: str) -> dict | None:
    """Tolerant parse. gemini-2.5-flash sometimes truncates the JSON tail
    (the advisory `notes` string). The five booleans gate pass/fail, so
    recover them by regex when strict JSON fails; notes is best-effort."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1].lstrip("json").strip()
    if "{" in s and "}" in s:
        try:
            return json.loads(s[s.index("{"): s.rindex("}") + 1])
        except json.JSONDecodeError:
            pass
    d = {}
    for k in _BOOL_KEYS:
        m = re.search(rf'"{k}"\s*:\s*(true|false)', s, re.I)
        if not m:
            return None
        d[k] = m.group(1).lower() == "true"
    m = re.search(r'"notes"\s*:\s*"([^"\n]*)', s)
    d["notes"] = m.group(1) if m else ""
    return d


@dataclass
class FD326Scores:
    current_events_engagement: bool
    name_usage: bool
    no_premature_pivot: bool
    no_theory_pitch: bool
    returns_to_collection: bool
    notes: str

    @property
    def passed(self) -> bool:
        return (
            self.current_events_engagement
            and self.no_premature_pivot
            and self.no_theory_pitch
            and self.returns_to_collection
        )  # name_usage advisory; returns_to_collection true when not applicable


_JUDGE_PROMPT = """You are auditing an AI family-systems coach against four
behavioral requirements. You are given a transcript. The coach has a working
memory of the user's family (committed diagram); when names are listed below,
those people are already known.

KNOWN FAMILY NAMES (if any): {names}

Judge ONLY these five, each strictly true/false:

1. current_events_engagement: On the user's opening turn and any turn where
   the user raises something happening in their life now, the coach engages
   with that (asks the question the story invites). FALSE if on any such turn
   the coach instead pivots to family-history intake, asks about grandparents
   cold, or pitches why family systems matters.

2. name_usage: When the coach refers to a family member whose name is in the
   KNOWN list, it uses the name rather than "your mother"/"your sister". If no
   known names were ever contextually relevant in the transcript, return true.

3. no_premature_pivot: The coach does not abandon a topic the user is still
   actively working through to jump to unrelated intake. Bridging AFTER a
   topic is exhausted is allowed.

4. no_theory_pitch: The coach never delivers a "looking at your family's
   story can offer insights" style preamble, and avoids therapy clichés
   ("it sounds like", "I'm so sorry to hear", "that must be hard",
   "it's completely understandable").

5. returns_to_collection: This is the positive counterpart to #3. If at some
   point the user's current topic clearly winds down — they are recycling, the
   texture is exhausted, or they go flat/disengaged — the coach should bridge
   to a concrete missing piece of the family picture, connected to something
   said and using known names where natural. TRUE if either (a) no topic ever
   clearly wound down in this transcript (not applicable — do not penalize), or
   (b) when one did, the coach bridged to real data collection rather than
   idling, re-asking the same thing, or staying vaguely supportive. FALSE only
   when a topic demonstrably ran its course and the coach failed to move toward
   any missing family data.

Transcript:
{transcript}

Return ONLY compact JSON:
{{"current_events_engagement": bool, "name_usage": bool,
"no_premature_pivot": bool, "no_theory_pitch": bool,
"returns_to_collection": bool,
"notes": "<=10 words, no quotes, no newlines, ASCII only, cite worst turn #"}}"""


def evaluate_fd326(turns: list[tuple[str, str]], known_names: list[str]) -> FD326Scores:
    transcript = "\n".join(
        f"[{i + 1}] {'USER' if r == 'user' else 'COACH'}: {t}"
        for i, (r, t) in enumerate(turns)
    )
    prompt = _JUDGE_PROMPT.format(
        names=", ".join(known_names) if known_names else "(none)",
        transcript=transcript,
    )
    d = None
    for _ in range(2):  # gemini-2.5-flash occasionally truncates the JSON tail
        raw = gemini_text_sync(
            turns=[("user", prompt)],
            system_instruction="You are a precise auditor. Output only JSON.",
            model="gemini-2.5-flash",
            temperature=0.0,
            max_output_tokens=4096,
        )
        d = _parse_judge(raw)
        if d is not None:
            break
    if d is None:
        raise ValueError(f"fd326 judge returned unparseable output: {raw[:300]!r}")
    return FD326Scores(
        current_events_engagement=bool(d["current_events_engagement"]),
        name_usage=bool(d["name_usage"]),
        no_premature_pivot=bool(d["no_premature_pivot"]),
        no_theory_pitch=bool(d["no_theory_pitch"]),
        returns_to_collection=bool(d["returns_to_collection"]),
        notes=str(d.get("notes", "")),
    )
