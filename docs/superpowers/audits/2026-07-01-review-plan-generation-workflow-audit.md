# Review Plan Generation Workflow Audit

Date: 2026-07-01
Branch: `codex/review-plan-source-brief-audit-plan`
Scope: review-plan generation quality, speed, teacher requirements, regeneration consistency, and observability.

## Verdict

The main failure is architectural: the workflow sends raw classroom text or raw ASR transcript into downstream planning and writing without a persisted structured source layer.

Prompt tuning and schema normalization help, but they are late-stage repairs. The next implementation should add a version-scoped structured source brief, route teacher requirements into source analysis and planning, align runtime model/ASR contracts with class commentary where appropriate, and shorten the slow quality/revision path.

## Current Data Flow

```text
new text/file/audio
  -> raw_text or ASR raw_transcription
  -> _merge_review_plan_materials()
  -> lessons.summary
  -> review_plan_versions row
  -> _run_review_plan_generation_job()
  -> intake_normalizer: raw summary_text becomes materials[0]
  -> source_analyzer: marker-only topic extraction + first 500 chars evidence
  -> subject_router / scope_planner / time_allocator / task_blueprint
  -> parent_planner LLM
  -> prompt_bundle_builder
  -> plan_generator LLM
  -> local quality gate
  -> LLM quality reviewer
  -> revision LLM up to two attempts
  -> PDF

regenerate
  -> lesson.summary
  -> current version generation_options + same_lesson_materials
  -> new review_plan_versions row
  -> same generation chain
```

## Evidence From Code

- `app.py:993-1013` transcribes audio, converts the result to `raw_transcription`, merges same-lesson materials, and saves that merged raw text as the lesson summary. There is no source cleanup or structure stage between ASR and generation.
- `app.py:7781-7838` regeneration reads `lesson.summary` and copies current version settings/materials. It does not use a stable source artifact owned by the version.
- `review_plan_workflow/nodes/intake_normalizer.py:19-50` checks missing fields and then stores `summary_text.strip()` as the only material. It does not segment, clean, classify, or extract evidence.
- `review_plan_workflow/nodes/source_analyzer.py:8-35` only looks for markers such as `本节课主题：`, `主题：`, or `topic:` and stores `text[:500]` as evidence. This is not structured preprocessing.
- `review_plan_workflow/service.py:414-502` already has a multi-node generation graph, but there is no source brief node before planner and writer.
- `review_plan_workflow/nodes/parent_planner.py:48-63` sends subject, topic, weak points, lesson date, and full `summary_text` to the parent planner. It does not include `user_requirements`.
- `review_plan_workflow/nodes/prompt_bundle_builder.py:49-55` includes `generation_options.user_requirements` for the prompt bundle.
- `review_plan_workflow/nodes/plan_generator.py:41-66` passes teacher requirements to writer and includes full classroom summary in the user message.
- `review_plan_workflow/nodes/revision.py:44-48` passes teacher requirements to revision.
- `review_plan_workflow/llm/client.py:21` defines `REVIEW_PLAN_LLM_TIMEOUT_SECONDS = 180.0`, while production logs show revision stages can still consume about 540 seconds, likely because provider/client retries multiply the effective wait.
- `config_runtime.py:62-67` sets nonzero generation temperatures: planner `0.25`, writer `0.35`, repair/reviewer `0.1`. Regeneration is therefore not deterministic.
- `config_runtime.py:221-249` separates review-plan parent model config from writer model config: parent uses `XR_REVIEW_PLAN_PROVIDER` / `XR_REVIEW_PLAN_MODEL`, while writer uses `XR_REVIEW_PLAN_WRITER_PROVIDER` / `XR_REVIEW_PLAN_WRITER_MODEL`; the DeepSeek writer fallback resolves to `deepseek-v4-pro`.
- `ai_processor.py:2195-2212` uses one `transcribe_audio()` path for audio, selecting Tencent ASR when `XR_AUDIO_TRANSCRIPTION_PROVIDER=tencent` and local faster-whisper otherwise.
- `app.py:993-1002` review-plan audio generation calls the same `transcribe_audio()` helper, but the charge/trace metadata is still hard-coded as `provider="local"` and `model="faster-whisper-base"`. This can make review-plan ASR look different from class commentary even when runtime config uses Tencent.
- `app.py:1156-1213` class commentary records audio transcription with runtime ASR provider/model metadata, saves raw transcript, then runs transcript polish before feedback generation.

## Production Evidence

Recent read-only production checks on `review_plan_runs` showed the issue is not a frontend polling problem. The slow path is backend LLM orchestration.

```text
lesson 81, run 18, 2026-07-01
status: succeeded
quality score: 0
parent_planner: 163809 ms
plan_generator: 224888 ms
quality_reviewer_llm: 336427 ms
revision: failed after 542634 ms with Request timed out
total wall clock: about 21 minutes

lesson 81, run 16, 2026-07-01
quality score: 0
parent_planner: 145277 ms
plan_generator: 212576 ms
quality_reviewer_llm: 98741 ms
revision: failed after 542680 ms
warning: plan_generator_schema_repair_failed

lesson 80, runs 14 and 15, 2026-06-29
quality score: 25
common warning: missing_input topic
revision timeout: about 542-545 seconds
quality issues: repeated printable tasks, factual drift, empty/generic topic, low-density PDF pages
```

### Production Runtime Configuration

Read-only PM2 environment checks on `xingrun` showed the current production contract is only partially aligned:

- Review-plan parent currently runs `XR_REVIEW_PLAN_PROVIDER=openai` with `XR_REVIEW_PLAN_MODEL=gpt-5.4`. Target: `gpt-5.5`.
- Review-plan writer provider/model are not explicitly set in PM2. Code fallback makes a DeepSeek writer resolve to `deepseek-v4-pro`, but production should still pin `XR_REVIEW_PLAN_WRITER_PROVIDER=deepseek` and `XR_REVIEW_PLAN_WRITER_MODEL=deepseek-v4-pro` to remove ambiguity.
- Class commentary currently runs `XR_CLASS_COMMENTARY_PROVIDER=openai` and `XR_CLASS_COMMENTARY_MODEL=gpt-5.5`.
- Audio transcription currently runs `XR_AUDIO_TRANSCRIPTION_PROVIDER=tencent` and `XR_TENCENT_ASR_ENGINE_TYPE=16k_zh`; Tencent credential presence is confirmed without exposing values.
- Global DeepSeek default is `deepseek-v4-flash`, so review-plan writer behavior must not be inferred from global `XR_DEEPSEEK_MODEL`.

Target runtime contract:

```text
review-plan ASR: Tencent Cloud ASR, same provider path as class commentary
XR_AUDIO_TRANSCRIPTION_PROVIDER=tencent
XR_TENCENT_ASR_ENGINE_TYPE=16k_zh
review-plan transcript polish: OpenAI gpt-5.5 before source brief
review-plan parent/planner: OpenAI gpt-5.5
XR_REVIEW_PLAN_PROVIDER=openai
XR_REVIEW_PLAN_MODEL=gpt-5.5
review-plan writer: DeepSeek deepseek-v4-pro
XR_REVIEW_PLAN_WRITER_PROVIDER=deepseek
XR_REVIEW_PLAN_WRITER_MODEL=deepseek-v4-pro
class commentary transcript polish/generation: OpenAI gpt-5.5
XR_CLASS_COMMENTARY_PROVIDER=openai
XR_CLASS_COMMENTARY_MODEL=gpt-5.5
```

## External Implementation Patterns

Shallow lesson-plan generator repos usually implement:

```text
teacher form
  -> one prompt
  -> lesson plan text
```

That pattern is not enough for classroom transcript to printable review PDF. Examples:

- `https://github.com/DivanshiJain2005/AI-lesson-planner`
- `https://github.com/daveymason/ai-lesson-planner`

Transcript and meeting summarization systems are more relevant. They usually implement:

```text
raw audio/transcript
  -> transcription
  -> cleaning / diarization / segmentation
  -> structured notes or action items
  -> final artifact
```

Relevant references:

- `https://github.com/hossamrizk/Done-Talking`
- `https://github.com/finnless/yt-summarizer`
- `https://developers.openai.com/api/docs/guides/structured-outputs`
- `https://docs.langchain.com/oss/python/langchain/structured-output`
- `https://docs.langchain.com/oss/python/langgraph/graph-api`
- `https://langfuse.com/docs/observability/overview`

## Focus Area Findings

### 1. Source Preprocessing

Severity: P1

Current state: raw text or ASR text is treated as the source of truth. The workflow does not persist a cleaned transcript, source brief, evidence map, or topic/confidence artifact. Review-plan audio does not currently have the class-commentary style transcript polish stage.

Impact:

- Dirty ASR filler, repeated phrases, incomplete problem stems, and teacher/student side comments consume tokens.
- Topic inference is fragile when the teacher did not type a `主题：` marker.
- Writer and reviewer must solve source understanding and document generation in one pass.
- Regeneration cannot know which exact source structure produced the prior output.

Recommendation: add a version-scoped `ReviewPlanSourceBrief` before parent planner and writer. For audio input, the chain should be Tencent ASR, OpenAI `gpt-5.5` transcript polish, then source brief extraction.

### 2. Output Quality

Severity: P1

Current state: the quality gate catches many issues, but too late. Production examples show score 0 or 25 with succeeded status and failed revision.

Common failures:

- Empty or generic `lesson_info.topic`.
- Full review topics are generic or evidence-free.
- Printable tasks are missing, repeated, or not independently answerable.
- Choices collapse into checklist-like questions.
- Writer returns wrapped or nested structures such as `plan.days`.
- Quotes drift into prompt-like or invented teacher lines.

Recommendation: move the quality control upstream by generating from source brief and evidence snippets, then keep local deterministic quality as the first gate.

### 3. Speed

Severity: P1

Current state: one generation can run 10-20 minutes because parent planner, writer, LLM reviewer, and revision all operate on large payloads.

Main bottlenecks:

- Full raw transcript appears in parent planner and writer inputs.
- LLM reviewer receives full generated plan JSON.
- Revision can wait about 9 minutes because provider/client retries compound timeouts.
- LLM reviewer runs even when local rules may be enough for straightforward pass/fail.

Recommendation:

- Use a compact source brief for planner/writer.
- Add transcript polish for audio sources, but keep it bounded and use its shorter cleaned text to reduce downstream token load.
- Add stage-specific timeouts and disable automatic retries for review-plan LLM calls.
- Run LLM reviewer only when local quality is suspicious, failed, or the source confidence is low.
- Cap revision to one fast targeted attempt in production until reliability improves.

### 4. Teacher Prompt Integration

Severity: P1

Current state: teacher requirements reach writer and revision, but not source analysis or parent planner.

Impact:

- The parent blueprint can plan a default review strategy, while the writer later tries to obey teacher constraints.
- Teacher requirements such as "压缩到一天", "多做选择诊断", or "少一点题量" are applied too late.

Recommendation: pass `user_requirements` into source brief extraction, parent planner payload, prompt bundle variables, writer, revision, and observability summaries. Treat it as a planning constraint that cannot override factuality, schema, PDF safety, or quality gate rules.

### 5. New Generation vs Regeneration

Severity: P1

Current state: new generation and regeneration can produce different results.

Causes:

- Nonzero temperatures.
- Regeneration reads `lesson.summary`, not a version-owned source snapshot.
- Regeneration can run under newer prompts/code/models than the original version.
- Regeneration dialog can carry different generation options or missing historical teacher requirements.
- No stored structured source brief exists to make "same source, new settings" explicit.

Recommendation: define regeneration as "reuse the version source artifact by default, then rerun planning/writing with current options." If the teacher edits source text later, rebuild the source brief explicitly.

## Existing Assets To Reuse

- `review_plan_workflow/service.py` already has the graph-like orchestration point.
- `review_plan_workflow/schemas.py` already uses Pydantic contracts.
- `review_plan_workflow/quality_gate.py` already has deterministic PDF-readiness checks.
- `review_plan_workflow/observability.py` already sends privacy-preserving Langfuse traces.
- `review_plan_versions` already gives a version boundary for persisted source artifacts.
- Class commentary has a useful precedent: `app.py:1156-1213` transcribes class commentary through runtime ASR config, saves raw transcript, then runs OpenAI `gpt-5.5` transcript polish before feedback generation.

## Target Data Flow

```text
raw source
  -> source ingestion
      audio: Tencent ASR through the shared transcribe_audio path
      audio: OpenAI gpt-5.5 transcript polish
      source_text snapshot
      cleaned_source_text
      structured source_brief
      evidence_map
      source_text_hash
  -> planning
      source_brief + teacher requirements + schedule
  -> writer
      compact source brief + evidence snippets + parent blueprint
  -> local quality gate
      pass and source confidence high -> PDF
      suspicious or failed -> LLM reviewer
      high issue and repairable -> one capped revision attempt
  -> PDF + run metrics

regenerate
  -> reuse source_text + source_brief from selected/current version
  -> apply new generation options and teacher requirements
  -> create new version without overwriting previous ready PDF
```

## Proposed Source Brief Contract

```json
{
  "source_text_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "cleaned_text": "cleaned transcript or text",
  "lesson_title_candidates": ["动点与立体几何综合"],
  "knowledge_points": [
    {
      "name": "定长线段对应球面轨迹",
      "evidence_ids": ["ev-001"],
      "confidence": 0.86
    }
  ],
  "method_chains": [
    {
      "name": "动点轨迹判断",
      "steps": ["固定量", "轨迹对象", "边界条件"],
      "evidence_ids": ["ev-002"]
    }
  ],
  "common_mistakes": [
    {
      "name": "把空间轨迹看成平面圆",
      "evidence_ids": ["ev-003"]
    }
  ],
  "example_stems": [
    {
      "stem": "动点 P 到定点 O 的距离恒为 r",
      "evidence_ids": ["ev-004"]
    }
  ],
  "teacher_emphasis": [
    {
      "quote": "先看固定量，再判断轨迹",
      "evidence_ids": ["ev-005"]
    }
  ],
  "excluded_noise": ["口头重复", "无关寒暄"],
  "missing_fields": ["topic"],
  "evidence_map": [
    {
      "id": "ev-001",
      "source": "summary_text",
      "quote": "到定点距离固定时，轨迹是球面。",
      "offset_start": 120,
      "offset_end": 148
    }
  ],
  "confidence": 0.82
}
```

## Implementation Risks

- Adding source brief can become another slow LLM call if it sends the full transcript with high reasoning settings. Mitigation: deterministic cleaner first, compact LLM extraction, fast model, strict timeout, fallback to deterministic brief.
- Adding transcript polish can become another slow LLM call if it is treated as an unbounded rewrite. Mitigation: use OpenAI `gpt-5.5` with a correction-only prompt, strict timeout, no meaning changes, and raw-transcript fallback.
- Runtime config can drift between parent model, writer model, ASR provider, and trace metadata. Mitigation: add explicit env pins and startup/deploy assertions for `gpt-5.5`, `deepseek-v4-pro`, and Tencent ASR metadata.
- Persisting source artifacts on version rows changes regeneration semantics. Mitigation: legacy fallback reads `lesson.summary` when version source fields are empty.
- Skipping LLM reviewer can let subtle issues through. Mitigation: only skip when local score is high, no high issues, source confidence is high, schema passes, and PDF smoke checks pass.
- Frontend copy can become explanatory again. Mitigation: use compact labels only: `源材料`, `生成要求`, `复习日期`, `复用原材料`.

## Verification Needed

- Unit tests for source cleaning and source brief extraction.
- Unit tests proving review-plan parent resolves to OpenAI `gpt-5.5`, writer resolves to DeepSeek `deepseek-v4-pro`, and audio transcription metadata uses Tencent `flash-16k_zh` when configured.
- Tests for review-plan transcript polish that prove it runs before source brief for audio input and falls back safely when polish fails.
- Store tests proving version source artifacts persist and hydrate.
- Workflow tests proving parent planner and writer receive source brief and teacher requirements.
- API tests proving regeneration reuses source artifacts and does not overwrite current PDFs.
- Speed-policy tests proving LLM reviewer/revision can be skipped or capped.
- Observability tests proving Langfuse includes source metrics and hashes but never full classroom text.
- Eval fixtures for lesson 80 pure text and lesson 81 dynamic geometry/solid geometry failures.
- PDF extraction proof for a generated plan that previously produced low-density or checklist-like output.

## Definition Of Done

- New generation stores `source_text`, `cleaned_source_text`, `source_brief_json`, and source hashes on the generated version.
- Review-plan audio uses the same Tencent ASR provider path and metadata as class commentary.
- Review-plan audio transcript polish uses OpenAI `gpt-5.5` before source brief.
- Review-plan parent is pinned to OpenAI `gpt-5.5`; review-plan writer is explicitly pinned to DeepSeek `deepseek-v4-pro`.
- Regeneration reuses the selected/current version source artifact unless source rebuilding is explicitly requested.
- Teacher requirements enter source brief, parent planner, writer, revision, and trace summaries.
- Planner/writer prompts use source brief and evidence snippets instead of repeating the full dirty transcript.
- Production slow path has bounded LLM calls and cannot spend about 9 minutes on one revision attempt.
- Local tests and evals include the real failure modes: missing topic, nested/wrapped schema, repeated printable tasks, checklist-like choices, and dynamic geometry source ambiguity.
