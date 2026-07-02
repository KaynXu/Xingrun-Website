# Review Plan Stable Generation Chain Plan

Date: 2026-07-02
Branch: `codex/review-plan-chain-audit`
Goal: make review-plan generation reliable, fast, and comparable across new generation, regeneration, preview, PDF, and future DOCX.

## Architecture

Target flow:

```text
text / PDF / PPT / DOCX / audio
-> LessonSourcePack
-> lesson_review_plan_v1
-> validator
-> evaluator when needed
-> targeted repair when needed
-> renderer
```

Non-goals:

- Do not build a multi-agent loop.
- Do not let LLM generate final HTML/CSS/DOCX layout.
- Do not add a large framework migration before contracts are stable.

## Phase 0: Hotfixes From Lesson 100

### Task 0.1: Read Latest Completed Quality Run

Files:

- `lesson_manager.py`
- `app.py`
- `tests/test_review_plan_async_api.py`

Change:

- Add `get_latest_completed_review_plan_quality_run_for_version(version_id)`.
- It should filter to completed/succeeded runs with non-empty quality review.
- Use it in `_review_plan_quality_failure_message()`.
- Do not allow later empty `running/interrupted` telemetry runs to hide a failed quality result.

Tests:

- Version has old failed quality run and newer empty interrupted run: failure message still returns failed quality reason.
- Version has newer passing completed quality run: failure message empty.

Acceptance:

- A version cannot be marked ready while its latest completed quality result is failed.

### Task 0.2: Stop PDF Choice Truncation

Files:

- `review_plan_templates/single_lesson_pdf.py`
- `tests/test_single_lesson_pdf_unification.py`

Change:

- Replace `explicit_choices[:2]` with all explicit choices that pass rendering rules.
- If visual density needs a cap, expose it as a validator rule, not a hidden renderer truncation.

Tests:

- Day with 5 blanks and 3 choices renders 8 questions and answer key has 8 answers.
- Lesson 100 fixture renders exactly 10 questions when the plan contains 10 printable questions.

Acceptance:

- PDF visible question count equals canonical printable question count.

### Task 0.3: Parse Teacher Count Constraints

Files:

- `review_plan_workflow/generation_options.py`
- `review_plan_workflow/schemas.py`
- `review_plan_workflow/quality_gate.py`
- `review_plan_workflow/nodes/parent_planner.py`
- `review_plan_workflow/nodes/plan_generator.py`
- `tests/test_review_plan_workflow.py`

Change:

- Add `GenerationConstraint`.
- Parse `题目控制在10道题`, `10题`, `选择题多一点`, `不要全是选择题`, `只要当天`, etc.
- Treat parsed count as hard validator input.
- Keep raw teacher prompt for LLM context.

Tests:

- `题目控制在10道题` requires exactly 10 visible printable questions.
- Missing parsed count falls back to current minimum density rules.
- User count cannot override schema, safety, or answer correctness.

Acceptance:

- Teacher prompt constraints are validated deterministically.

### Task 0.4: Strengthen Source Brief Title And Heading Extraction

Files:

- `review_plan_workflow/source_brief.py`
- `tests/test_review_plan_source_brief.py`

Change:

- Treat first non-empty line as a title candidate when it looks like a classroom title.
- Extract headings like `第一部分：`, `一、`, `二、`, `课堂收尾`.
- Extract topic-like noun phrases from section headings.
- Extract teacher action cues like `必须背熟`, `课后作业`, `明天抽查`.

Tests:

- Provided transcript extracts title candidate containing `勾股数`.
- Provided transcript extracts at least 5 knowledge points/method chains.
- Marker-based extraction still works.

Acceptance:

- Rich transcripts do not fall into `topic=null`, `knowledge_points=[]`, `lesson_title_candidates=[]`.

### Task 0.5: Tolerate Nullable Reviewer Fields

Files:

- `review_plan_workflow/schemas.py`
- `review_plan_workflow/nodes/llm_quality_reviewer.py`
- `tests/test_review_plan_workflow.py`

Change:

- Normalize nullable reviewer fields such as `question_type=null` to empty strings.
- Keep target-path parsing tolerant.

Acceptance:

- A useful reviewer result is not discarded because one optional locator field is null.

## Phase 1: Canonical Contracts

### Task 1.1: Define LessonSourcePack

Files:

- `review_plan_workflow/source_pack.py`
- `review_plan_workflow/schemas.py`
- `lesson_manager.py`
- migration in existing schema bootstrap

Fields:

```text
source_id
source_type
title
language
segments[]
detected_topics[]
math_blocks[]
teacher_actions[]
warnings[]
source_hash
created_at
```

Rules:

- Text/PDF/PPT/DOCX/audio transcript all enter this format.
- Audio ASR result is cached before source pack creation.
- Source pack is version-owned.

Tests:

- Same text produces stable hash and segment IDs.
- Regeneration reuses current version source pack by default.

### Task 1.2: Define lesson_review_plan_v1

Files:

- `review_plan_workflow/plan_v1.py`
- `review_plan_workflow/schemas.py`
- `review_plan_workflow/nodes/plan_generator.py`
- `review_plan_workflow/nodes/revision.py`

Fields:

```text
schema_version
document_title
audience
lesson_summary
knowledge_map[]
review_schedule[]
practice_tasks[]
self_check_questions[]
math_blocks[]
teacher_checkpoints[]
uncertainties[]
source_coverage[]
```

Rules:

- LLM returns only `lesson_review_plan_v1`.
- Legacy `days/blanks/choices/task_blocks` conversion moves to a compatibility adapter.
- New validator and renderer consume v1 directly.

Tests:

- Wrapped fields like `plan.days` fail schema.
- Missing answers fail schema.
- Old stored version still renders through compatibility adapter.

### Task 1.3: One Printable Count Function

Files:

- `review_plan_workflow/printable_questions.py`
- `review_plan_workflow/quality_gate.py`
- `review_plan_templates/single_lesson_pdf.py`
- preview/frontend later

Change:

- Create one canonical counting function.
- It returns:
  - total visible questions
  - per-day count
  - answer-key count
  - dropped/unrenderable items

Acceptance:

- Validator, PDF, and tests use the same count logic.

## Phase 2: Validator And Evaluator Split

### Task 2.1: Deterministic Validator

Files:

- `review_plan_workflow/validator.py`
- `tests/test_review_plan_validator.py`

Checks:

- schema valid
- days match exactly
- teacher constraints satisfied
- visible questions equal answer-key entries
- every task has action and output
- every self-check has answer
- math placeholders resolve
- source coverage segment IDs exist
- renderer dry run has zero dropped items

Acceptance:

- Validator catches Lesson 100 before ready because 10 requested but only 7 visible.

### Task 2.2: Bounded Evaluator

Files:

- `review_plan_workflow/evaluator.py`
- `review_plan_workflow/quality_policy.py`
- `review_plan_workflow/nodes/llm_quality_reviewer.py`

Rules:

- Run only after validator pass or validator soft warnings.
- Do not evaluate broken schema.
- Return structured categories:
  - pedagogy
  - source_confidence
  - factuality
  - workload
  - style

Acceptance:

- Low source confidence can warn without blocking.
- Wrong math answer blocks.

### Task 2.3: Targeted Repair Only

Files:

- `review_plan_workflow/nodes/question_repair.py`
- `review_plan_workflow/nodes/revision.py`
- `review_plan_workflow/service.py`

Rules:

- Question-level issue repairs only the question.
- Source coverage issue repairs only coverage metadata or uncertainty text.
- Full-plan revision only for schema-level failures.
- Maximum one repair attempt by default.

Acceptance:

- One wrong choice answer does not trigger full JSON rewrite.

## Phase 3: Speed And Cache

### Task 3.1: Source Cache

Files:

- `lesson_manager.py`
- `review_plan_workflow/source_pack.py`

Cache keys:

```text
raw_source_hash
cleaned_source_hash
source_pack_schema_version
parser_version
```

Acceptance:

- Regenerating from unchanged source does not rerun ASR or document parsing.

### Task 3.2: Fast Path And High-Quality Path

Files:

- `review_plan_workflow/service.py`
- `review_plan_workflow/observability.py`

Fast path:

```text
source pack
-> writer
-> validator
```

High-quality path:

```text
fast path
-> evaluator
-> targeted repair
-> validator
```

Acceptance:

- Fast path: no more than 2 model calls after ASR.
- High-quality path: no more than 3 model calls after ASR.
- Stage timing is visible in Langfuse and local run logs.

### Task 3.3: Long Input Map-Reduce

Files:

- `review_plan_workflow/source_pack.py`
- `review_plan_workflow/source_brief.py`

Change:

- Split long inputs by sections/time windows.
- Extract local topics/examples/formulas per segment.
- Reduce into one source pack.
- Cache segment-level extraction.

Acceptance:

- Long transcript coverage improves without generating a full plan per chunk.

## Phase 4: Renderer Contract

### Task 4.1: Renderer Dry Run

Files:

- `review_plan_templates/single_lesson_pdf.py`
- `review_plan_workflow/renderer_contract.py`

Change:

- Renderer reports dropped items, visible question count, answer count, formula failures.
- Quality validator consumes this report before saving ready.

Acceptance:

- Hidden renderer truncation cannot ship.

### Task 4.2: Preview Math

Files:

- frontend review-plan detail/preview modules
- backend serializer for `math_blocks`

Change:

- Render math placeholders with KaTeX or MathJax.
- Show readable fallback if formula fails.

Acceptance:

- Preview renders formula blocks correctly for math/physics fixtures.

### Task 4.3: DOCX Export Path

Decision:

- First pass can keep readable LaTeX in DOCX if timeline is tight.
- If math/physics export is core for launch, use Pandoc to convert Markdown/LaTeX math to DOCX OMML.

Acceptance:

- PDF/preview are correct first.
- DOCX does not silently corrupt formulas.

## Phase 5: Observability And Evals

### Task 5.1: Langfuse Trace Fields

Fields:

- source_hash
- source_type
- source_pack_confidence
- generation_mode
- parsed_teacher_constraints
- model_call_count
- validator_result
- evaluator_result
- repair_count
- visible_question_count
- answer_key_count
- renderer_dropped_count
- latency_by_stage

Acceptance:

- A failed or low-quality generation can be diagnosed without reading raw student material.

### Task 5.2: Regression Corpus

Fixtures:

- Lesson 100 pythagorean alpha/beta one-day 10-question request
- Dynamic geometry task_blocks case
- Sections/questions normalization case
- Low-evidence text-only case
- Wrong math answer repair case
- Formula transport case
- Regeneration same-source case

Acceptance:

- CI can detect visible question count regressions and source extraction regressions.

## Phase 6: Product Semantics

### Task 6.1: Generation Modes

Keep user-facing labels explicit:

- `当天课后复习`: one-day compressed review for today's class.
- `5次间隔复习`: days 1, 2, 7, 14, 30.
- `每日连续复习`: day 1 through N.
- `自定义日期`: selected day offsets.

Acceptance:

- No PDF or frontend copy says `第1天集中复习` for compressed mode.

### Task 6.2: Regenerate vs Re-render

Add product distinction:

- Regenerate: model call, new version, same source pack unless edited.
- Re-render PDF: no model call, same plan content, new file output.

Acceptance:

- Teachers can fix display/export issues without changing generated content.

## Implementation Order

Recommended order:

1. Phase 0 hotfixes.
2. Phase 1 canonical contracts.
3. Phase 2 validator/evaluator split.
4. Phase 3 cache and speed.
5. Phase 4 renderer/DOCX.
6. Phase 5 evals and observability.
7. Phase 6 product semantics.

Do not start Phase 4 DOCX formula perfection before Phase 0 and Phase 1 are stable.

## Global Acceptance Criteria

- Lesson 100 with `题目控制在10道题` produces exactly 10 visible questions and 10 answers.
- No failed latest completed quality review can be hidden by later empty runs.
- PDF visible question count equals canonical printable count.
- Source pack extracts title and key sections from the provided transcript.
- Compressed mode says `当天课后复习`, never `第1天集中复习`.
- New generation and regeneration obey the same source/constraint contracts.
- Fast path stays within 2 model calls after ASR.
- High-quality path stays within 3 model calls after ASR.
- Renderer never silently drops generated questions.

## Verification Commands For Implementation

Run after Phase 0 code changes:

```bash
python3 -m py_compile app.py lesson_manager.py review_plan_workflow/source_brief.py review_plan_workflow/quality_gate.py review_plan_workflow/schemas.py review_plan_templates/single_lesson_pdf.py
python3 -m unittest tests.test_review_plan_workflow tests.test_review_plan_async_api tests.test_single_lesson_pdf_unification -v
git diff --check
```

Run after canonical contract work:

```bash
python3 -m unittest tests.test_review_plan_source_brief tests.test_review_plan_workflow tests.test_review_plan_evals tests.test_single_lesson_pdf_unification -v
cd frontend && npm run build
git diff --check
```
