# Zoom Transcript Processing Workflow

How to turn a Zoom meeting recording into structured meeting artifacts.

## File Naming Convention

All meeting files: `YYYY-MM-DD-<ai-generated-summary-slug>.<ext>`

Examples:
- `2026-02-16-sarah-round1-calibration-transcript.txt`
- `2026-02-16-sarah-round1-calibration-deliberation.md`
- `2026-02-16-sarah-round1-calibration-notes.md`

## Artifact Chain (per meeting)

| Artifact | Template | Purpose |
|----------|----------|---------|
| Raw transcript | — | Irreplaceable ground truth, always committed |
| Deliberation record | `DELIBERATION_TEMPLATE.md` | Lossless structured transformation of the transcript |
| Meeting notes | `TEMPLATE.md` | Conclusions-only quick reference |
| Results snapshot | — | Point-in-time aggregation in `results/YYYY-MM-DD-irr-results.md`. **One per meeting, never edit previous snapshots.** |

## Deliberation Record: Purpose and Quality Standard

The deliberation record is the primary high-fidelity data artifact. Its purpose is to capture the full diversity of independent opinions and how they evolve through discussion — preserving both agreement AND unresolved ambiguity for later AI-driven meta-analysis.

**Why this matters (CI theory):** Per the collective intelligence literature (Surowiecki, Hong & Page, Lorenz et al.), the value of group calibration comes from maintaining cognitive diversity while building shared rules. The deliberation record must preserve:
- **Independent positions** (initial codings before discussion) — the raw diversity
- **Arguments and evidence** (what each coder cited and why) — the reasoning behind diversity
- **Position evolution** (who shifted, what triggered it, genuine insight vs. accommodation) — the quality of aggregation
- **Resolution status** (unanimous / unresolved / deferred) — the confidence level of convergence

**Downstream products derivable from these records across N meetings:**
1. **Coding rules with confidence scores** — where the group converged, with the arguments that drove convergence and the number of meetings it took
2. **Unresolved ambiguity map** — where they didn't converge, the competing positions, and the quality of arguments on each side
3. **Coder trajectory analysis** — how each individual's coding approach evolved over time
4. **Rule evolution history** — how specific rules were proposed, debated, refined, or abandoned across meetings

**Exhaustiveness rule:** Every substantive point in the transcript MUST appear in the deliberation record. Err on the side of inclusion:

- Every argument, counter-argument, and theoretical reference made by any participant
- Every proposed heuristic, rule, or methodological suggestion — even tangential ones
- Every personal anecdote or concrete example cited as evidence
- Every process observation (format critiques, tooling issues, scheduling)
- Every cross-cutting meta-discussion (process improvement, methodology evolution)
- Every reference to external work, literature, or historical precedent
- Operational mechanics clarifications (how the coder works, data model details)
- Post-meeting side conversations captured in the recording

Do NOT omit a point because it seems tangential or minor. The transcript is the ground truth; the deliberation record must be a lossless structured transformation of it (excluding only pure social pleasantries).

## After Each Meeting

### 1. Get the transcript

Zoom Settings > Recording must have transcript enabled.

After the meeting:
1. Go to Zoom > Recordings > [meeting]
2. Download transcript (.vtt or .txt)
3. Save to `btcopilot/doc/irr/meetings/` with naming convention

**If Zoom transcript is missing** (recording was local-only or transcript wasn't enabled):

1. Extract audio: `ffmpeg -i recording.mp4 -vn -acodec libmp3lame -q:a 4 /tmp/audio.mp3 -y`
2. Transcribe with AssemblyAI (API key in `.env`, free tier = 100 hours):
   ```bash
   ASSEMBLYAI_API_KEY=... uv run python -c "
   import assemblyai as aai, os
   aai.settings.api_key = os.environ['ASSEMBLYAI_API_KEY']
   t = aai.Transcriber().transcribe('/tmp/audio.mp3',
       config=aai.TranscriptionConfig(speaker_labels=True, language_code='en'))
   with open('btcopilot/doc/irr/meetings/YYYY-MM-DD-slug-transcript.txt', 'w') as f:
       f.writelines(f'Speaker {u.speaker}: {u.text}\n' for u in t.utterances)
   "
   ```
3. Map speaker labels (A, B, C...) to names manually
4. Clean up: `rm /tmp/audio.mp3`

### 2. Ask Claude Code to process it

Drop the transcript file and prompt:

> Process this Zoom IRR calibration transcript into a deliberation record and meeting notes.
> Templates: btcopilot/doc/irr/meetings/DELIBERATION_TEMPLATE.md and TEMPLATE.md.
> Case: [Sarah]. Meeting number: [N].
> Update GUIDELINES.md and PROGRESS.md with any new rules/status.

Claude Code will:
- Read the transcript **exhaustively** — every substantive point must be captured
- Create **deliberation record** (per-statement: positions, reasoning, arguments, position evolution, resolution, ambiguity signals, rules). Refer to statements by their database ID (e.g. "Statement 1844"), not by ordinal index (e.g. "Statement 1"). Must include ALL arguments, heuristics, anecdotes, references, process observations, and meta-discussions from the transcript. See the exhaustiveness rule above.
- Create **meeting notes** (conclusions only: disagreement tables, resolutions, rules, action items)
- Update GUIDELINES.md with new rules
- Update PROGRESS.md (meeting log + session log)
- Update README.md (meetings table + results snapshots table)
- Create a new **results snapshot** in `results/` (see Step 4)

### 3. Review the output

Check:
- **Deliberation record exhaustiveness** — Does every substantive point from the transcript appear? Go through the transcript line by line and verify no arguments, heuristics, anecdotes, references, process observations, or meta-discussions were omitted. The deliberation record must be a lossless structured transformation of the transcript (excluding only pure social pleasantries). This is the most important quality gate.
- Deliberation record — coder reasoning attributed correctly? Arguments captured?
- Meeting notes — conclusions accurate?
- `GUIDELINES.md` — rules captured correctly?
- `PROGRESS.md` — status updated?

### 4. Create results snapshot (MANDATORY — do not defer or skip)

Create a new timestamped results snapshot: `results/YYYY-MM-DD-irr-results.md`

**Results snapshots are cumulative.** Each snapshot is a full point-in-time aggregation of ALL prior IRR products: study maturity, measurement approach status, quantitative metrics, coding rules registry (all rules from all meetings up to this point), unresolved ambiguities (updated with current status), coder status (cumulative attendance and cases), and product pipeline. The snapshot must be self-contained — a reader should be able to understand the full state of the study from this file alone without reading previous snapshots.

**Rules:**
- New file each time — never edit a previous snapshot
- Must incorporate all findings from the current meeting AND all prior meetings
- If processing meetings out of chronological order, create the missing snapshot first, then verify the later snapshot is consistent with it
- Update the README.md Results Snapshots table to link to the new snapshot

### 5. Verify completeness (MANDATORY)

Before committing, verify every artifact exists. **All 7 must be present or the processing is incomplete:**

| # | Artifact | Location | Check |
|---|----------|----------|-------|
| 1 | Raw transcript | `meetings/YYYY-MM-DD-*-transcript.*` | File exists |
| 2 | Deliberation record | `meetings/YYYY-MM-DD-*-deliberation.md` | File exists, exhaustiveness audit done |
| 3 | Meeting notes | `meetings/YYYY-MM-DD-*-notes.md` | File exists |
| 4 | Results snapshot | `results/YYYY-MM-DD-irr-results.md` | File exists, cumulative, self-contained |
| 5 | GUIDELINES.md | Updated revision history row | New rules added if any |
| 6 | PROGRESS.md | Meeting log + session log rows | Meeting entry added |
| 7 | README.md | Meetings table + results table rows | Both tables updated |

### 6. Commit

Commit all artifacts: transcript, deliberation record, meeting notes, results snapshot, and updated GUIDELINES.md / PROGRESS.md / README.md.

## Notes

- Raw transcripts ARE committed to the repo — they are the irreplaceable ground truth
- Deliberation records are a lossless structured transformation of the transcript
- Guidelines accumulate across meetings
- If the IRR dashboard is working, check `/training/irr/` after any re-coding
