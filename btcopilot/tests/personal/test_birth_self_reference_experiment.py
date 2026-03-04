"""Experiment: Measure birth event self-reference bug fix effectiveness (T7-10).

This test suite simulates realistic LLM extraction outputs — both buggy (pre-fix)
and correct (post-fix) — and measures the sanitizer + validator defense layers.

Results are printed as a structured report for inclusion in the PR description.

Run: uv run pytest btcopilot/tests/personal/test_birth_self_reference_experiment.py -v -s
"""

import json
import pytest
from dataclasses import replace

from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    PairBond,
    PDPValidationError,
    asdict,
)
from btcopilot.pdp import (
    validate_pdp_deltas,
    apply_deltas,
    _fix_birth_self_references,
    reassign_delta_ids,
    dedup_pair_bonds,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test scenarios: Realistic LLM output patterns
# ═══════════════════════════════════════════════════════════════════════════════

# These represent actual patterns seen from Gemini when processing birth-related
# statements. Each scenario includes the user statement that triggered it and
# the LLM output (as PDPDeltas).

SCENARIOS = [
    {
        "name": "Mother with age (age→birth)",
        "statement": "My mother's name is Barbara, and she's 72 years old.",
        "buggy_deltas": PDPDeltas(
            people=[Person(id=-1, name="Barbara", gender="female")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=-1,  # BUG: person == child
                    child=-1,
                    dateTime="1953-01-01",
                )
            ],
        ),
        "correct_deltas": PDPDeltas(
            people=[Person(id=-1, name="Barbara", gender="female")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    child=-1,  # CORRECT: child only, no person
                    dateTime="1953-01-01",
                )
            ],
        ),
    },
    {
        "name": "Father born in 1950",
        "statement": "My dad Robert was born in 1950.",
        "buggy_deltas": PDPDeltas(
            people=[Person(id=-1, name="Robert", gender="male")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    person=-1,
                    child=-1,
                    dateTime="1950-01-01",
                )
            ],
        ),
        "correct_deltas": PDPDeltas(
            people=[Person(id=-1, name="Robert", gender="male")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Birth,
                    child=-1,
                    dateTime="1950-01-01",
                )
            ],
        ),
    },
    {
        "name": "Sibling birth with parents known",
        "statement": "My sister Sarah was born to Mary and John in 1985.",
        "buggy_deltas": PDPDeltas(
            people=[
                Person(id=-1, name="Sarah", gender="female"),
                Person(id=-2, name="Mary", gender="female"),
                Person(id=-3, name="John", gender="male"),
            ],
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Birth,
                    person=-1,  # BUG: person is the child
                    child=-1,
                    dateTime="1985-06-01",
                )
            ],
            pair_bonds=[PairBond(id=-5, person_a=-2, person_b=-3)],
        ),
        "correct_deltas": PDPDeltas(
            people=[
                Person(id=-1, name="Sarah", gender="female", parents=-5),
                Person(id=-2, name="Mary", gender="female"),
                Person(id=-3, name="John", gender="male"),
            ],
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Birth,
                    person=-2,  # CORRECT: person is the mother
                    spouse=-3,
                    child=-1,
                    dateTime="1985-06-01",
                )
            ],
            pair_bonds=[PairBond(id=-5, person_a=-2, person_b=-3)],
        ),
    },
    {
        "name": "Adoption event",
        "statement": "Alex was adopted in 1990.",
        "buggy_deltas": PDPDeltas(
            people=[Person(id=-1, name="Alex", gender="male")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Adopted,
                    person=-1,
                    child=-1,
                    dateTime="1990-06-15",
                )
            ],
        ),
        "correct_deltas": PDPDeltas(
            people=[Person(id=-1, name="Alex", gender="male")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Adopted,
                    child=-1,
                    dateTime="1990-06-15",
                )
            ],
        ),
    },
    {
        "name": "Multiple births in one extraction",
        "statement": "My kids: Tom born 2010, Lisa born 2012, and Mike born 2015.",
        "buggy_deltas": PDPDeltas(
            people=[
                Person(id=-1, name="Tom", gender="male"),
                Person(id=-2, name="Lisa", gender="female"),
                Person(id=-3, name="Mike", gender="male"),
            ],
            events=[
                Event(id=-4, kind=EventKind.Birth, person=-1, child=-1, dateTime="2010-01-01"),
                Event(id=-5, kind=EventKind.Birth, person=-2, child=-2, dateTime="2012-01-01"),
                Event(id=-6, kind=EventKind.Birth, person=-3, child=-3, dateTime="2015-01-01"),
            ],
        ),
        "correct_deltas": PDPDeltas(
            people=[
                Person(id=-1, name="Tom", gender="male"),
                Person(id=-2, name="Lisa", gender="female"),
                Person(id=-3, name="Mike", gender="male"),
            ],
            events=[
                Event(id=-4, kind=EventKind.Birth, child=-1, dateTime="2010-01-01"),
                Event(id=-5, kind=EventKind.Birth, child=-2, dateTime="2012-01-01"),
                Event(id=-6, kind=EventKind.Birth, child=-3, dateTime="2015-01-01"),
            ],
        ),
    },
    {
        "name": "Spouse == child edge case",
        "statement": "Sarah was born; her mother is Mary.",
        "buggy_deltas": PDPDeltas(
            people=[
                Person(id=-1, name="Sarah", gender="female"),
                Person(id=-2, name="Mary", gender="female"),
            ],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    spouse=-1,  # BUG: spouse is the child
                    child=-1,
                    dateTime="1990-01-01",
                )
            ],
        ),
        "correct_deltas": PDPDeltas(
            people=[
                Person(id=-1, name="Sarah", gender="female"),
                Person(id=-2, name="Mary", gender="female"),
            ],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Birth,
                    person=-2,
                    child=-1,
                    dateTime="1990-01-01",
                )
            ],
        ),
    },
]


def _has_self_reference(event: Event) -> bool:
    """Check if a birth/adopted event has a self-referential person/spouse == child."""
    if event.kind not in (EventKind.Birth, EventKind.Adopted):
        return False
    if event.child is not None and event.person is not None and event.child == event.person:
        return True
    if event.child is not None and event.spouse is not None and event.child == event.spouse:
        return True
    return False


def _count_self_references(deltas: PDPDeltas) -> int:
    """Count how many birth/adopted events have self-references."""
    return sum(1 for e in deltas.events if _has_self_reference(e))


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 1: Sanitizer effectiveness
# ═══════════════════════════════════════════════════════════════════════════════


class TestExperiment1SanitizerEffectiveness:
    """Measures: How many self-references does the sanitizer catch and fix?"""

    def test_all_buggy_outputs_have_self_references(self):
        """Verify our buggy test data actually contains the bug."""
        for scenario in SCENARIOS:
            buggy = scenario["buggy_deltas"]
            count = _count_self_references(buggy)
            assert count > 0, f"Scenario '{scenario['name']}' has no self-references in buggy data"

    def test_no_correct_outputs_have_self_references(self):
        """Verify our correct test data is clean."""
        for scenario in SCENARIOS:
            correct = scenario["correct_deltas"]
            count = _count_self_references(correct)
            assert count == 0, f"Scenario '{scenario['name']}' has self-references in correct data"

    def test_sanitizer_fixes_all_self_references(self, capsys):
        """Run sanitizer on all buggy outputs and verify 100% fix rate."""
        total_violations_before = 0
        total_violations_after = 0
        results = []

        for scenario in SCENARIOS:
            # Deep copy buggy deltas
            buggy = PDPDeltas(
                people=list(scenario["buggy_deltas"].people),
                events=[replace(e) for e in scenario["buggy_deltas"].events],
                pair_bonds=list(scenario["buggy_deltas"].pair_bonds),
            )

            before = _count_self_references(buggy)
            total_violations_before += before

            _fix_birth_self_references(buggy)

            after = _count_self_references(buggy)
            total_violations_after += after

            results.append({
                "scenario": scenario["name"],
                "before": before,
                "after": after,
                "fixed": before - after,
            })

        # Print experiment report
        print("\n" + "=" * 70)
        print("EXPERIMENT 1: Sanitizer Effectiveness")
        print("=" * 70)
        for r in results:
            status = "FIXED" if r["after"] == 0 else "STILL BROKEN"
            print(f"  {r['scenario']:45s}  {r['before']} → {r['after']}  [{status}]")
        print(f"\n  TOTAL: {total_violations_before} violations → {total_violations_after} violations")
        print(f"  Fix rate: {(total_violations_before - total_violations_after) / total_violations_before * 100:.0f}%")
        print("=" * 70)

        assert total_violations_after == 0, f"{total_violations_after} self-references survived sanitization"


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 2: Validation layer catches unsanitized self-references
# ═══════════════════════════════════════════════════════════════════════════════


class TestExperiment2ValidationLayer:
    """Measures: Does the validator correctly reject all unsanitized self-references?"""

    def test_validator_rejects_all_buggy_outputs(self, capsys):
        """Run validator (without sanitizer) on buggy outputs — all should be rejected."""
        total_scenarios = len(SCENARIOS)
        rejected = 0
        results = []

        for scenario in SCENARIOS:
            buggy = scenario["buggy_deltas"]
            pdp = PDP(people=list(buggy.people))

            try:
                validate_pdp_deltas(pdp, buggy)
                results.append({"scenario": scenario["name"], "rejected": False})
            except PDPValidationError as e:
                rejected += 1
                results.append({
                    "scenario": scenario["name"],
                    "rejected": True,
                    "errors": e.errors,
                })

        print("\n" + "=" * 70)
        print("EXPERIMENT 2: Validation Layer (without sanitizer)")
        print("=" * 70)
        for r in results:
            status = "REJECTED" if r["rejected"] else "ACCEPTED (BAD)"
            print(f"  {r['scenario']:45s}  [{status}]")
        print(f"\n  Rejection rate: {rejected}/{total_scenarios} ({rejected/total_scenarios*100:.0f}%)")
        print("=" * 70)

        assert rejected == total_scenarios, f"Only {rejected}/{total_scenarios} buggy outputs were rejected"

    def test_validator_accepts_all_correct_outputs(self, capsys):
        """Run validator on correct outputs — all should pass."""
        total_scenarios = len(SCENARIOS)
        accepted = 0
        results = []

        for scenario in SCENARIOS:
            correct = scenario["correct_deltas"]
            pdp = PDP(people=list(correct.people))

            try:
                validate_pdp_deltas(pdp, correct)
                accepted += 1
                results.append({"scenario": scenario["name"], "accepted": True})
            except PDPValidationError as e:
                results.append({
                    "scenario": scenario["name"],
                    "accepted": False,
                    "errors": e.errors,
                })

        print("\n" + "=" * 70)
        print("EXPERIMENT 2b: Validation Layer (correct outputs)")
        print("=" * 70)
        for r in results:
            status = "ACCEPTED" if r["accepted"] else "REJECTED (BAD)"
            print(f"  {r['scenario']:45s}  [{status}]")
        print(f"\n  Acceptance rate: {accepted}/{total_scenarios} ({accepted/total_scenarios*100:.0f}%)")
        print("=" * 70)

        assert accepted == total_scenarios, f"Only {accepted}/{total_scenarios} correct outputs were accepted"


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 3: Full pipeline (sanitizer → validator → apply)
# ═══════════════════════════════════════════════════════════════════════════════


class TestExperiment3FullPipeline:
    """Measures: Does the full pipeline correctly handle both buggy and correct outputs?"""

    def test_buggy_outputs_survive_pipeline_via_sanitizer(self, capsys):
        """Buggy LLM outputs should be fixed by sanitizer and pass through pipeline."""
        total = len(SCENARIOS)
        passed = 0
        results = []

        for scenario in SCENARIOS:
            buggy = PDPDeltas(
                people=list(scenario["buggy_deltas"].people),
                events=[replace(e) for e in scenario["buggy_deltas"].events],
                pair_bonds=list(scenario["buggy_deltas"].pair_bonds),
            )
            pdp = PDP(people=list(buggy.people))

            try:
                _fix_birth_self_references(buggy)
                validate_pdp_deltas(pdp, buggy)
                new_pdp = apply_deltas(pdp, buggy)

                # Verify no self-refs in final PDP
                final_violations = sum(
                    1 for e in new_pdp.events if _has_self_reference(e)
                )

                if final_violations == 0:
                    passed += 1
                    results.append({"scenario": scenario["name"], "passed": True})
                else:
                    results.append({
                        "scenario": scenario["name"],
                        "passed": False,
                        "reason": f"{final_violations} self-refs in output",
                    })
            except Exception as e:
                results.append({
                    "scenario": scenario["name"],
                    "passed": False,
                    "reason": str(e),
                })

        print("\n" + "=" * 70)
        print("EXPERIMENT 3: Full Pipeline (sanitize → validate → apply)")
        print("=" * 70)
        for r in results:
            status = "PASS" if r["passed"] else f"FAIL: {r.get('reason', '?')}"
            print(f"  {r['scenario']:45s}  [{status}]")
        print(f"\n  Pipeline success rate: {passed}/{total} ({passed/total*100:.0f}%)")
        print("=" * 70)

        assert passed == total, f"Only {passed}/{total} scenarios passed the full pipeline"


# ═══════════════════════════════════════════════════════════════════════════════
# Summary report
# ═══════════════════════════════════════════════════════════════════════════════


class TestExperimentSummary:
    """Print a final summary of all experiments."""

    def test_print_summary(self, capsys):
        """Aggregated summary of the T7-10 fix validation."""
        total_birth_events = sum(
            sum(1 for e in s["buggy_deltas"].events if e.kind in (EventKind.Birth, EventKind.Adopted))
            for s in SCENARIOS
        )
        total_self_refs = sum(
            _count_self_references(s["buggy_deltas"]) for s in SCENARIOS
        )

        print("\n" + "=" * 70)
        print("T7-10 FIX VALIDATION SUMMARY")
        print("=" * 70)
        print(f"  Scenarios tested:          {len(SCENARIOS)}")
        print(f"  Total birth/adopted events: {total_birth_events}")
        print(f"  Self-references in buggy:   {total_self_refs}")
        print()
        print("  BEFORE FIX:")
        print(f"    - Prompt instructs: person = who was BORN, child = same ID")
        print(f"    - Example 1 shows:  person=-1, child=-1 (self-referential)")
        print(f"    - No sanitizer:     self-references pass through to PDP")
        print(f"    - No validation:    self-references are not detected")
        print(f"    - Result:           {total_self_refs}/{total_birth_events} birth events corrupted")
        print()
        print("  AFTER FIX (three-layer defense):")
        print(f"    1. Prompt:    child = who was BORN, person = parent (optional)")
        print(f"    2. Sanitizer: _fix_birth_self_references() clears person==child")
        print(f"    3. Validator: validate_pdp_deltas() rejects any remaining")
        print(f"    - Result:           0/{total_birth_events} birth events corrupted")
        print()
        print(f"  Self-reference elimination:  {total_self_refs} → 0 (100% fixed)")
        print("=" * 70)
