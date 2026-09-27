# Kept live runs

One results file per live eval run whose change was kept, copied here with why it was kept:

    uv run python -m btcopilot.tests.live.record btcopilot/tests/live/results/<run>.json "<why it was kept>"

Commit the copy. The next release loads every file here into the quality dashboard's table
(`flask admin quality load`), together with the old extraction F1 history in
`doc/f1/f1_timeseries.json`; loading again changes nothing. A run that stopped partway is
never kept.
