"""What the pull-request workflow runs, and which step holds the store's key."""

import yaml

from btcopilot.tests.repo import REPO

CI = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
STEPS = [step for job in CI["jobs"].values() for step in job["steps"]]
KEY = "SOPS_AGE_KEY"


def test_only_the_guards_step_holds_the_store_key():
    # R-0451
    assert [step.get("name") for step in STEPS if KEY in str(step)] == [
        "Run the oracle guards"
    ]
    assert KEY not in str(CI.get("env")) + str([job.get("env") for job in CI["jobs"].values()])


def test_the_suite_that_reads_the_prompts_runs_without_the_guards():
    # R-0451
    runs = {step.get("name"): step.get("run", "") for step in STEPS}
    assert '-m "not conventions"' in runs["Run unit tests"]
    assert "-m conventions" in runs["Run the oracle guards"]
