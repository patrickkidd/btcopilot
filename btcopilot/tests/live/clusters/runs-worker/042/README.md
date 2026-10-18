# Tries of job 042

Ten tries per case of cluster detection, on Bedrock, each folder with its ledger lines.

| Folder | Model | Head | Ledger |
|--------|-------|------|--------|
| `2026-10-18T112620-claude-haiku-4-5-20251001-round1` | Haiku 4.5 | 280b57b8 | `ledger.jsonl`, its Haiku lines |
| `2026-10-18T115905-claude-sonnet-5` | Sonnet 5, thinking off | 280b57b8 | `ledger.jsonl`, its Sonnet lines |
| `2026-10-18T132913-claude-haiku-4-5-20251001-round2` | Haiku 4.5 | 81978261 | `round2-ledger.jsonl` |

Round 1 and the Sonnet tries were measured on 280b57b8, before the word list that marks a
shift as a standing pattern was narrowed to "always" and "forever", in code and in the prompt
(83832b78, 69a6bb0f, 81978261). Round 2 is Haiku again on 81978261. The round 1 folder was
renamed after its tries; its files are unchanged.

Sonnet was not tried again on 81978261. Its failure is that no first answer could be read:
cut off at the length limit on deep and deep-unasked, and not the JSON asked for on the other
cases. The word list does not touch either.

The tries of each folder were made by several processes at once, one per case or per five
tries, and copied into one folder. Two Sonnet tries lost in the middle of a call were made
again; the lost calls are in no ledger (about $0.30).

Each folder replays at $0 to the same score, misses, refusals and stored clusters as its
files, 90 of 90 each:

    CLUSTER_ANSWERS=<folder> CLUSTER_TRIES=10 LIVE_REPLAY=only CLUSTER_LEDGER=<a scratch file> \
        SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt uv run pytest btcopilot/tests/live/clusters --e2e
