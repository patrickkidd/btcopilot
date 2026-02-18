# Cut-off Fix + Prompt Refinements

**Date**: 2026-02-18 ~16:42 UTC
**Session**: 9e478072-df36-4009-8b8e-45f6f502174d (continued)
**Files modified**: `btcopilot/tests/personal/synthetic.py`

## Problem: Mid-Sentence Truncation

Discussion 54 (Adrian, dismissive-avoidant) had widespread mid-sentence cut-offs:
- "No one complained then because"
- "It" (single word)
- "Growing up, she was always the"
- "I think he was"
- "and then I go back to"

**Root cause**: `max_output_tokens` is a hard stop. The model doesn't know it's about to be cut off, so it can't wrap up its thought. The structural token limits from the previous session were being used as both the length control *and* the ceiling — they were too tight.

## Fix: Prompt-Based Word Targets + Generous Ceilings

Replaced the approach of using `max_output_tokens` as the primary length control:

| | Before | After |
|--|--------|-------|
| Length signal | `max_output_tokens` only | Word target in prompt |
| Token limit | Tight (25-300 tokens) | Generous ceiling (120-400 tokens) |
| Model awareness | None — hard stop | Sees target, can self-regulate |
| Safety net | None | `_trim_to_sentence()` trims to last period |

New `_RESPONSE_MODES`:
```python
"short":  {"words": (15, 40),   "ceiling": 120}
"medium": {"words": (60, 120),  "ceiling": 250}
"long":   {"words": (130, 220), "ceiling": 400}
```

Prompt now includes: `**Length: ~{word_target} words.** Finish your thought completely — do not trail off mid-sentence.`

## Evaluation: Discussion 55 (Evan)

Evan — dismissive-avoidant IT professional, evasive/terse traits, presenting problem: "interpersonal style" barrier to promotion.

### What worked
- **Zero cut-offs** — every response ends at a natural sentence boundary
- **Character voice strong** — consistent IT metaphors: "buffer overflow," "power save mode," "redundant data," "glitch in the system"
- **Natural resistance** — "Why are we talking about my uncles?", "Why does it matter how he reacted?"
- **Genuine short responses** — "It was during my quarterly review. I closed a ticket without explaining the fix to the client." (15 words)
- **Average 120 words/turn** (down from 271 baseline)

### Remaining concerns identified

1. **Consecutive long streaks in deep phase** — turns 18-20 all 170-240 words. A guarded client would oscillate more after disclosing something vulnerable.

2. **Rhetorical question pattern** — too many turns end with deflecting questions: "Why complicate things?", "Why would I want to change that?", "Does that make sense?" Becomes formulaic by turn 10.

3. **Self-insight too polished** — "my brain is programmed to go into power save mode" and "I'm using a proven survival strategy but it's costing me a promotion" are therapist-level observations. A real dismissive-avoidant client wouldn't narrate their own defense mechanisms — they'd say "I don't know why it bugs me."

4. **Repeated verbal tics** — "Anyway, it's fine" appeared in both turns 18 and 19.

## Fixes Applied

### Anti-pattern additions (`_ANTI_PATTERNS`)
- **Self-insight guard**: "You do NOT have clinical insight into your own defense mechanisms. You don't know why you do what you do — you just do it. If you notice a pattern, express confusion about it, not understanding."
- **Rhetorical question limit**: "Don't end responses with rhetorical questions more than once or twice in the whole conversation."
- **Verbal tic variation**: "Don't repeat the same verbal tic across multiple turns."

### Structural: post-long-response bias
After a response >100 words, the next turn's mode weights shift: "long" probability drops to 20% of base, "short" gets +0.3 bonus. Prevents monologue streaks without making the pattern mechanical.

## Clinical Observations

Evan's conversation is clinically interesting: the IT metaphors ("power save mode," "buffer overflow," "redundant data") are the character maintaining emotional distance through intellectualization — a classic dismissive-avoidant pattern. The coach correctly identifies this and the parallels to his father's "wall" behavior. The concern is that the *client* is also identifying it too clearly, which breaks realism. A real client with this level of avoidance would need the coach to make those connections, not arrive at them independently.

The "Anyway, it's fine" verbal tic is actually realistic for a dismissive client — the problem was just repetition within adjacent turns. Real clients do have tics, but they vary: "it's fine," "whatever," "I don't know," "it is what it is."
