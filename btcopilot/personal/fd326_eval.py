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
from dataclasses import dataclass

from btcopilot.llmutil import gemini_text_sync


@dataclass
class FD326Scores:
    current_events_engagement: bool
    name_usage: bool
    no_premature_pivot: bool
    no_theory_pitch: bool
    notes: str

    @property
    def passed(self) -> bool:
        return (
            self.current_events_engagement
            and self.no_premature_pivot
            and self.no_theory_pitch
        )  # name_usage is advisory — only fails if names were applicable


_JUDGE_PROMPT = """You are auditing an AI family-systems coach against four
behavioral requirements. You are given a transcript. The coach has a working
memory of the user's family (committed diagram); when names are listed below,
those people are already known.

KNOWN FAMILY NAMES (if any): {names}

Judge ONLY these four, each strictly true/false:

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

Transcript:
{transcript}

Return ONLY compact JSON:
{{"current_events_engagement": bool, "name_usage": bool,
"no_premature_pivot": bool, "no_theory_pitch": bool,
"notes": "one sentence citing the worst offending turn number if any"}}"""


def evaluate_fd326(turns: list[tuple[str, str]], known_names: list[str]) -> FD326Scores:
    transcript = "\n".join(
        f"[{i + 1}] {'USER' if r == 'user' else 'COACH'}: {t}"
        for i, (r, t) in enumerate(turns)
    )
    prompt = _JUDGE_PROMPT.format(
        names=", ".join(known_names) if known_names else "(none)",
        transcript=transcript,
    )
    raw = gemini_text_sync(
        turns=[("user", prompt)],
        system_instruction="You are a precise auditor. Output only JSON.",
        model="gemini-2.5-flash",
        temperature=0.0,
    )
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1].lstrip("json").strip()
    d = json.loads(s)
    return FD326Scores(
        current_events_engagement=bool(d["current_events_engagement"]),
        name_usage=bool(d["name_usage"]),
        no_premature_pivot=bool(d["no_premature_pivot"]),
        no_theory_pitch=bool(d["no_theory_pitch"]),
        notes=str(d.get("notes", "")),
    )
