"""The grouping call on the fictional Hale record: three runs of events decades
apart and two strays, the shape of the fault seen on production. The old
prompt let the model fold them into one group of fifty years; the reworded
prompt and the ten-year check keep them three (R-0833, R-0834, R-0835).
Invented names only; no real record is involved.

The app's grouping model is Gemini, and this suite's machine may have no key
for it, so the call goes through Claude Code (`claude -p` with the answer's
JSON schema), the way the coach cases run on the subscription (README.md).
LIVE_CLUSTER_MODEL names the model; the default is the one this machine's
Claude Code reaches. Each call's cost as Claude Code reports it is printed, so
the run's spend is in the output and in the ledger entry the log carries.
"""

import json
import os
import re
import subprocess
import tempfile
from decimal import Decimal

from btcopilot.clusters import (
    ClusterError,
    ClusterListResponse,
    ModelCluster,
    detect_clusters,
)
from btcopilot.tests.live.criterion import once, passes
from btcopilot.tests.test_clusters import ALL_HALE, HALE, HALE_NAMES, HALE_STORED

MODEL = os.environ.get("LIVE_CLUSTER_MODEL", "us.anthropic.claude-opus-5")
# The app sends the grouping prompt with no system prompt of its own; Claude
# Code's own is replaced by one line so nothing about coding reaches the model.
SYSTEM = "Answer with the JSON the schema asks for and nothing else."
TIMEOUT = 600
spent: list[Decimal] = []


def ask(prompt: str, schema: dict, limit: int) -> ClusterListResponse:
    """One grouping answer from Claude Code, in the shape the app's model gives."""
    env = dict(os.environ, CLAUDE_CODE_MAX_OUTPUT_TOKENS=str(limit))
    with tempfile.TemporaryDirectory() as cwd:
        ran = subprocess.run(
            [
                "claude",
                "-p",
                "--output-format",
                "json",
                "--model",
                MODEL,
                "--system-prompt",
                SYSTEM,
                "--tools",
                "",
                # the structured answer is a tool call of Claude Code's own and
                # then the message; some models take a turn for each
                "--max-turns",
                "3",
                "--setting-sources",
                "",
                "--strict-mcp-config",
                "--no-session-persistence",
                "--json-schema",
                json.dumps(schema),
            ],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=TIMEOUT,
        )
    if ran.returncode and not ran.stdout.strip():
        raise RuntimeError(f"claude -p failed: {ran.stderr.strip()[:500]}")
    result = json.loads(ran.stdout)
    if result.get("is_error"):
        raise RuntimeError(
            f"claude -p failed: {result.get('subtype')} "
            f"{result.get('api_error_status')} {result.get('result')} "
            f"{ran.stderr.strip()[:300]}"
        )
    spent.append(Decimal(str(result.get("total_cost_usd") or 0)))
    print(f"  {MODEL}: ${spent[-1]:.4f}, {sum(spent):.4f} so far")
    answer = result.get("structured_output") or json.loads(result["result"])
    return ClusterListResponse(
        clusters=[ModelCluster(**group) for group in answer.get("clusters", [])]
    )


def span(cluster) -> tuple[int, int]:
    return int(cluster.startDate[:4]), int(cluster.endDate[:4])


def names_outside(cluster, data) -> list[str]:
    """First names in the cluster's name that belong to no person on its events."""
    on_events = set()
    for chunk in data.events:
        if chunk["id"] in cluster.eventIds:
            on_events.update(
                chunk.get(key)
                for key in ("person", "spouse", "child")
                if chunk.get(key)
            )
            on_events.update(chunk.get("relationshipTargets") or [])
    allowed = {HALE_NAMES[person - 1] for person in on_events}
    return [name for name in HALE_NAMES if name in cluster.name and name not in allowed]


def years_outside(cluster) -> list[int]:
    first, last = span(cluster)
    said = [
        int(y)
        for y in re.findall(
            r"\b(1[89]\d\d|20\d\d)\b", f"{cluster.name} {cluster.reason}"
        )
    ]
    return [y for y in said if not first <= y <= last]


@passes(8, of=10)
def test_three_runs_decades_apart_stay_three_groups():
    # R-0833, R-0834
    """The 1950s, 1994 and 1996 to 2001 come back as three groups; the 1948
    marriage joins none of them; no group spans 1955 and 1994; the grandfather's
    1998 death sits in the 1996 to 2001 group or in none; and no name or reason
    reaches outside its own events."""
    result = detect_clusters(HALE, ask)
    for cluster in result.clusters:
        print(
            f"  {span(cluster)} {cluster.eventIds} {cluster.name!r}: {cluster.reason}"
        )
    assert len(result.clusters) == 3, [c.eventIds for c in result.clusters]
    assert all(
        1 not in c.eventIds for c in result.clusters
    ), "the 1948 marriage joined a group"
    assert not [
        c for c in result.clusters if span(c)[0] <= 1955 and span(c)[1] >= 1994
    ], "a group spans 1955 and 1994"
    holding_death = [c for c in result.clusters if 11 in c.eventIds]
    assert all(
        9 in c.eventIds for c in holding_death
    ), "the 1998 death joined the wrong group"
    assert not [years_outside(c) for c in result.clusters if years_outside(c)]
    assert not [
        names_outside(c, HALE) for c in result.clusters if names_outside(c, HALE)
    ]


@once
def test_a_stored_fifty_year_group_is_not_handed_back_unchanged():
    # R-0835
    """With the merged 1948 to 2001 group already stored as the model's, one
    real run either returns the groups inside it or is refused, which leads to
    the rules' groups under their years; the stored group never comes back as
    it was."""
    try:
        result = detect_clusters(HALE_STORED, ask)
    except ClusterError as refused:
        # both answers refused: in the turn this leads to the rules' groups
        # under their years, and the stored group is removed (R-0780, R-0835)
        print(f"  refused twice, the last by {refused.check.value}: {refused}")
        return
    for cluster in result.clusters:
        print(f"  {cluster.id} {span(cluster)} {cluster.eventIds} {cluster.name!r}")
    whole = [c for c in result.clusters if set(c.eventIds) == set(ALL_HALE)]
    assert not whole, "the fifty-year group came back as it was"
    assert not [
        c for c in result.clusters if span(c)[0] <= 1955 and span(c)[1] >= 1994
    ], "a group still spans 1955 and 1994"
