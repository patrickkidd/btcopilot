# Zoom Transcript Processing Workflow

How to turn a Zoom meeting recording into structured meeting notes.

## After Each Meeting

### 1. Get the transcript

Zoom Settings > Recording must have transcript enabled.

After the meeting:
1. Go to Zoom > Recordings > [meeting]
2. Download transcript (.vtt or .txt)
3. Save to `btcopilot/doc/irr/meetings/` temporarily

### 2. Ask Claude Code to process it

Drop the transcript file and prompt:

> Process this Zoom IRR calibration transcript into meeting notes.
> Use the template at btcopilot/doc/irr/meetings/TEMPLATE.md.
> Case: [Sarah]. Meeting number: [N].
> Update GUIDELINES.md and PROGRESS.md with any new rules/status.

Claude Code will:
- Read the transcript
- Identify disagreements discussed
- Map coder positions (S/A/R/F per coder per statement)
- Capture resolutions and rules
- Create the meeting note file
- Update GUIDELINES.md with new rules
- Update PROGRESS.md

### 3. Review the output

Zoom's speech-to-text will mangle clinical terms. Check:
- `meetings/meeting-N-*.md` -- accurate summary?
- `GUIDELINES.md` -- rules captured correctly?
- `PROGRESS.md` -- status updated?

### 4. Commit

Commit all changed files in `btcopilot/doc/irr/`.
Delete the raw transcript (it has no persistent value beyond the notes).

## Notes

- Raw transcripts are NOT committed to the repo
- Meeting notes are the persistent artifact
- Guidelines accumulate across meetings
- If the IRR dashboard is working, check `/training/irr/` after any re-coding
