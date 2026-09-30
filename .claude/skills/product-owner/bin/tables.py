"""Run the ledger's SQL queries on production in one read-only transaction and
print each query's rows as JSON, keyed by the loop name its heading in
doc/FEEDBACK_LOOPS.md carries ("goal: ..." for the G headings). Arguments pick
queries by the number before the heading's dot; none runs all.

    python3 tables.py            # every query
    python3 tables.py 10         # only "10. Which features people use"
"""

import csv
import io
import json
import re
import subprocess
import sys

from files import REPO

LEDGER = REPO / "doc" / "FEEDBACK_LOOPS.md"
PSQL = (
    "docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' fd-postgres "
    "psql -U familydiagram -d familydiagram -q --csv -v ON_ERROR_STOP=1"
)
MARK = "@@query"


def queries(picked):
    found = re.findall(
        r"^### (\w+)\. ([^\n]+)\n\n```sql\n(.*?)```", LEDGER.read_text(), re.S | re.M
    )
    return [
        (loop if number.isdigit() else f"goal: {loop}", part.strip())
        for number, loop, body in found
        if not picked or number in picked
        for part in body.split(";")
        if part.strip()
    ]


def main(picked):
    chosen = queries(picked)
    script = "".join(f"\\echo {MARK}{i}\n{sql};\n" for i, (_, sql) in enumerate(chosen))
    done = subprocess.run(
        ["ssh", "root@familydiagram", PSQL],
        input=script,
        capture_output=True,
        text=True,
    )
    if done.returncode:
        sys.exit(done.stderr)
    out = {}
    for block in done.stdout.split(MARK)[1:]:
        index, _, text = block.partition("\n")
        loop = chosen[int(index)][0]
        out.setdefault(loop, []).append(list(csv.DictReader(io.StringIO(text))))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(set(sys.argv[1:]))
