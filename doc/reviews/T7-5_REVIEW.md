# T7-5: Generate 3 Fresh Synthetic Discussions

## Generated Discussions

| Discussion ID | Persona | Traits | Attachment Style | Turns |
|--------------|---------|--------|-----------------|-------|
| **50** | Evan (persona id=3) | Defensive, Confused Dates | Dismissive-Avoidant | 20 |
| **51** | Chloe (persona id=5) | Oversharing, Emotional | Anxious-Preoccupied | 20 |
| **52** | Robert (persona id=6) | Terse, Evasive | Fearful-Avoidant | 20 |

All discussions generated with `skip_extraction` (chat only, no delta extraction per T7-3).

## Scripts Used
- `/tmp/generate_3_discussions.py` — generated discussions 50 and 51
- `/tmp/generate_3rd_discussion.py` — generated discussion 52 (after persona gen JSON parse failure on first attempt)

## Next Steps
- **T7-6**: Patrick codes GT in SARF editor for these 3 discussions
- **T7-7**: Run `extract_full()` on these discussions, compare via `calculate_cumulative_f1()`
