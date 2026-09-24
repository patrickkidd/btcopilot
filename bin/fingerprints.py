"""Pins each ruling id to the quotes behind it, for the id-stability guard.

  python bin/fingerprints.py      appends new ids and new quotes; rewrites nothing

Needs a sops key (SOPS_AGE_KEY_FILE or SOPS_AGE_KEY). The file holds ids and
hashes only, never text.
"""
from btcopilot import oracle
from btcopilot.tests.conventions.test_oracle import FINGERPRINTS

text = FINGERPRINTS.read_text() if FINGERPRINTS.exists() else ""
FINGERPRINTS.write_text(oracle.pin(text))
print(f"{len(oracle.pinned(FINGERPRINTS.read_text()))} ids pinned in {FINGERPRINTS}")
