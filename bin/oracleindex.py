"""Renders the oracle index (private/oracle/rulings.md) from the topic files and
the tests citing each ruling; the index is never edited by hand.

  python bin/oracleindex.py      rewrites the index only when its text changed

Needs a sops key (SOPS_AGE_KEY_FILE or SOPS_AGE_KEY).
"""
import subprocess

from btcopilot import oracle
from btcopilot.tests.conventions.test_oracle import citations

text = oracle.listing(citations())
if oracle.INDEX.exists() and oracle.index() == text:
    print(f"{oracle.INDEX} unchanged")
else:
    subprocess.run(
        ["sops", "-e", "--filename-override", str(oracle.INDEX.relative_to(oracle.ROOT)),
         "--output", str(oracle.INDEX), "/dev/stdin"],
        cwd=oracle.ROOT, input=text, text=True, check=True,
    )
    print(f"{len(text.encode())} bytes, {len(oracle.rulings())} rulings in {oracle.INDEX}")
