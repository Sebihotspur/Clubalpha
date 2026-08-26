# Contextual Interaction — 2026-08-26

This directory freezes the first upcoming Premier League slate evaluated by
Contextual Interaction v1.

- `predictions.jsonl` preserves the full fixture-by-fixture baseline,
  directional channel calculations, contextual probabilities, and deltas.
- `report.json` is the compact ten-fixture comparison and provenance record.
- `results.jsonl` is an append-only stream for observed results. It is empty at
  freeze time and is deliberately excluded from immutable hashes.
- `manifest.json` hashes the predictions, report, model inputs, implementation,
  and this note.

The contextual output is a shadow sensitivity comparison. The locked base
forecast remains unchanged; neither forecast is authorized for capital
deployment. Never regenerate this dated archive in place. A future model or
coefficient must create a new dated archive.
