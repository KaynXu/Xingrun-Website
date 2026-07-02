# Review Plan Low-Evidence Gate Audit

Date: 2026-07-02

## Problem

Recent review-plan failures were not mainly prompt failures. The workflow treated weak classroom evidence as a hard quality failure:

- `source_brief` can legitimately miss `topic`, `knowledge_points`, or title candidates for short, noisy, or low-signal transcripts.
- The writer still has to produce printable questions and a usable plan.
- The LLM reviewer then reported inferred topics as `factuality/high`, so the version failed even when the document was otherwise usable.

This made generation success depend on enumerating every evidence-boundary edge case. That is too brittle.

## Current Chain

The relevant chain is:

1. `source_brief_builder` extracts structured classroom evidence.
2. `parent_planner` creates the teaching blueprint.
3. `plan_generator` writes the final JSON.
4. local quality gate checks schema, days, printable questions, PDF readiness, and obvious bad content.
5. LLM reviewer checks pedagogy and factuality when source confidence is low or local score is not high enough.
6. revision runs at most one or two attempts.
7. quality failure blocks PDF and marks the version failed.

The failure mode came from step 5 and 6: low evidence was mixed into the same hard lane as wrong answers and broken PDFs.

## New Policy

Hard failures remain:

- missing schema or review days
- no printable questions
- wrong math answer or factual error
- malformed choices or empty answers
- broken PDF/rendering text
- unsupported teacher quotes

Soft after one revision:

- source evidence is weak
- `source_brief` is missing topic or knowledge points
- generated topics are clearly marked as assumptions, fallback, or pending teacher confirmation
- plan is printable, self-contained, and grade/subject appropriate

The user should receive a document in this case, not a failed generation.

## Implementation

- `quality_policy.py` now distinguishes soft evidence issues from hard quality issues.
- `_maybe_revise_plan()` logs `quality_evidence_soft_pass` for low-evidence soft passes.
- `parent_planner`, `plan_generator`, `revision`, and `llm_quality_reviewer` prompts now explicitly allow usable fallback generation for weak sources.
- Tests lock the boundary:
  - low-source evidence issue soft-passes after one revision.
  - math answer errors stay hard.
  - schema/PDF failures stay hard.
  - workload-only issues keep the previous soft-pass behavior.

## Next Optimization

For a cleaner long-term contract, add explicit issue categories such as `source_confidence` or `evidence_gap` instead of encoding low-evidence behavior through `factuality` descriptions.
