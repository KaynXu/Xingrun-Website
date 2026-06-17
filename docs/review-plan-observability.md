# Review Plan Observability

## On-call questions

1. Which review-plan run failed or produced low-quality output, and what was its `trace_id`?
2. Which workflow node was slow or failed: intake, routing, source analysis, prompt bundle, plan generator, revision, or quality gate?
3. Which provider/model handled the chain and which provider/model handled the writer node?
4. Did the final plan pass the quality gate, and were schema repair or revision warnings involved?

## Signals

- SQLite `review_plan_runs` remains the source of truth for run status, node outputs, warnings, and quality review.
- Optional Langfuse tracing is enabled with `XR_REVIEW_PLAN_LANGFUSE_ENABLED=true`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL`.
- Langfuse root trace name: `review_plan.workflow`.
- Node span name format: `review_plan.node.<node_name>`.
- LLM generation name: `review_plan.llm.generate_json`.
- Quality score name: `review_plan_quality`.

## Privacy

Langfuse payloads intentionally avoid full classroom transcripts, full prompts, generated plan prose, tokens, and secrets. Inputs and outputs are summarized with counts, short safe previews for non-sensitive fields such as topic, and SHA-256 hashes for correlation.
