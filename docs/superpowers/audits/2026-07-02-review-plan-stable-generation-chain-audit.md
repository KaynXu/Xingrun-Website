# Review Plan Stable Generation Chain Audit

Date: 2026-07-02
Branch: `codex/review-plan-chain-audit`
Scope: review-plan generation quality, speed, teacher requirements, regeneration consistency, validation, and rendering.

## Verdict

The current chain has improved from raw prompt generation, but it is still not stable enough as a product contract.

The issue is not that the model cannot write a good review plan. The issue is that the system still lets too many responsibilities leak across stages:

```text
source understanding
output schema
teacher constraints
quality judgment
PDF rendering
delivery status
```

These must be split into stable contracts:

```text
text / PDF / PPT / DOCX / audio
-> LessonSourcePack
-> lesson_review_plan_v1 JSON
-> deterministic validator + bounded evaluator
-> controlled preview / PDF / DOCX renderer
```

Prompt fixes and retry loops can reduce symptoms, but they cannot guarantee visible question count, source coverage, reproducible regeneration, or fast generation by themselves.

## Case Evidence: Lesson 100 / Version 72

Production record:

```text
lesson_id=100
version_id=72
status=ready
generation_options={
  "schedule_mode": "compressed",
  "review_days": [1],
  "daily_count": 1,
  "user_requirements": "题目控制在10道题",
  "source": "create"
}
```

Online PDF:

```text
file: /Users/xiaodi/Downloads/勾股数、特殊角与和角推导-100-v1.pdf
pages: 3
extracted chars: 1235
visible question count: 5 blanks + 2 choices = 7
contains: 当天课后复习, 当天复习后应留下的内容
does not contain: 10题, 待确认, 30天后应留下的内容
```

Local Codex control PDF from the same classroom text and the same teacher requirement:

```text
file: /Users/xiaodi/Desktop/01_星润与复习计划/xingrun.web/lingshiwenjian/20260702-勾股数特殊角度αβ与和角推导-当天课后复习计划-10题对照版-20260702-194148.pdf
pages: 5
extracted chars: 2528
visible question count: 10
contains: 10题对照版, 当天课后复习, 当天复习后应留下的内容
```

Conclusion from this sample:

- The frontend/backend received the teacher requirement.
- The online chain did not enforce it as a deterministic contract.
- The PDF renderer dropped content from the generated structure.
- The final version became `ready` despite a failed quality run existing for the same version.

## Current Implementation Snapshot

Current flow on latest `origin/develop`:

```text
create / regenerate request
-> normalize_generation_options()
-> ReviewPlanInput
-> intake_normalizer
-> source_brief_builder
-> source_analyzer
-> subject_router
-> scope_planner
-> time_allocator
-> task_blueprint
-> parent_planner LLM with fallback
-> prompt_bundle_builder
-> plan_generator LLM
-> normalize_final_review_plan()
-> deterministic quality_gate
-> LLM quality reviewer when policy says needed
-> question_repair or revision
-> record quality
-> single_lesson_pdf renderer
```

This is materially better than the earlier raw-text-to-PDF chain. The remaining problem is that the internal objects are still partial and adapter-driven rather than being one canonical document contract.

## Findings

### P0: Delivery Status Can Hide A Failed Quality Result

Evidence:

- `app.py:895` uses `_review_plan_quality_failure_message(version_id)`.
- It calls `get_latest_review_plan_run_for_version(version_id)`.
- `lesson_manager.py:5757` returns the latest run by `updated_at DESC, id DESC`, regardless of whether that run has a real quality result.

Observed production behavior:

- Version 72 had a real quality result with `score=78`, `passed=false`, `must_revise=true`.
- Later empty or interrupted runs for the same version sorted newer.
- The delivery path read the wrong run, so the failed quality result did not block `ready`.

Fix direction:

- Add a version helper that returns the latest completed run with a non-empty `quality_review_json`.
- Use it for delivery failure messaging and ready/failed decision checks.
- Treat empty `running/interrupted` runs as task telemetry, not final quality truth.

Acceptance:

- A version with any latest completed failed quality review cannot become ready unless a newer completed passing quality review exists.

### P0: Teacher Prompt Is Advisory, Not A Hard Contract

Evidence:

- `generation_options.user_requirements` exists and is routed into `ReviewPlanInput`.
- `parent_planner`, `plan_generator`, `question_repair`, and prompts now receive it.
- The validator only enforces compressed mode minimum density: at least 5 printable questions for one-day compressed mode.

Observed behavior:

- Teacher asked `题目控制在10道题`.
- Online PDF delivered 7 visible questions.

Fix direction:

- Parse teacher requirements into a deterministic `GenerationConstraint` object before planning.
- Extract at least:
  - total printable question count
  - per-day question count
  - preferred question types
  - excluded question types
  - schedule intent
- Pass the raw teacher prompt to the LLM, but make parsed constraints the validator contract.

Acceptance:

- `题目控制在10道题` means exactly 10 visible printable questions and exactly 10 answer-key entries unless the system blocks with a user-readable reason before generation.

### P0: PDF Renderer Truncates Explicit Choices

Evidence:

- `review_plan_templates/single_lesson_pdf.py:410-421` collects all explicit choices.
- `choice_values = explicit_choices[:2]` drops all choices after the second one.

Observed behavior:

- Production `plan_json` had 3 choices.
- PDF rendered only 2 choices.

Fix direction:

- Render all normalized choices that pass PDF-readiness rules.
- If a template has a visual density limit, validator must know that limit and enforce it before PDF generation.
- PDF visible count must be compared with plan JSON printable count in tests.

Acceptance:

- Given 5 blanks and 3 choices in day 1, the PDF renders 8 questions and 8 answers.

### P1: Source Brief Is Useful But Too Shallow

Evidence:

- `review_plan_workflow/source_brief.py:25` title markers are limited to `本节课主题：`, `主题：`, and `topic:`.
- `_title_candidates()` only reads explicit topic or these markers.
- `_looks_like_knowledge_point()` only accepts configured markers like `知识点：`, `重点：`, `结论：`, `定理：`, `公式：`, `性质：`.
- The provided transcript starts with a natural title: `勾股数、特殊角度αβ与和角推导完整课堂逐字稿`, then section headings like `第一部分：...`, `一、奇数开头整数勾股数`.

Observed production behavior:

- `source_brief_json` had `topic=null`, `knowledge_points=[]`, and `lesson_title_candidates=[]`.
- This made downstream generation rely on fallback assumptions even though the transcript was rich.

Fix direction:

- Promote current `source_brief` into `LessonSourcePack`.
- Add deterministic extraction for:
  - first-line classroom title
  - Chinese section headings
  - enumerated knowledge lists
  - formula/math tokens
  - teacher action words such as `必须背熟`, `课后作业`, `明天抽查`
- Keep confidence explicit; low confidence should not fail a printable plan by itself.

Acceptance:

- The provided transcript yields a title candidate containing `勾股数` and at least 5 knowledge points/method chains before the generator runs.

### P1: Output Contract Is Still Legacy-Adapter Based

Evidence:

- The current generator must output a JSON object that the existing `normalize_final_review_plan()` and `single_lesson_pdf.py` adapter can understand.
- Recent fixes had to normalize `sections[].questions` and `task_blocks` into `days[].blanks/choices/items`.

Impact:

- The writer can generate content in multiple plausible shapes.
- Quality gate and PDF renderer may disagree on what is printable.
- New fields require adapter patches instead of schema evolution.

Fix direction:

- Define `lesson_review_plan_v1` as the only accepted generated output.
- Keep backward adapters only at the boundary for old stored versions.
- Validator and renderer should read the same canonical object.

Acceptance:

- There is one canonical function for printable question count, used by validator, PDF renderer, preview, and tests.

### P1: Quality Gate Is Correct In Spirit But Too Mixed In Responsibility

Current hard checks include:

- schema/review days
- printable question presence
- topic/full review topic density
- choices completeness
- formula transport damage
- placeholder text
- math/factual errors from LLM reviewer

Problem:

- Product readiness, source evidence confidence, pedagogy, and renderer safety are mixed into one pass/fail lane.
- This caused earlier low-evidence plans to fail too often.
- Recent soft-pass policy helps, but it is still description-based and fragile.

Fix direction:

Split checks:

```text
validator
  deterministic, cheap, no LLM
  schema, visible count, answer key, days, renderer safety, math block references

evaluator
  bounded LLM
  pedagogy, appropriateness, missing key concepts, evidence drift

repair
  only targeted fields/questions
  one bounded attempt by default
```

Acceptance:

- A source-evidence warning cannot block a plan that is printable, self-contained, and marked as fallback.
- A wrong answer, broken formula, missing answer key, or renderer mismatch still blocks.

### P1: Speed Is Still Driven By Large Payload LLM Calls

Current improvements:

- Parent planner fallback exists.
- LLM reviewer can be skipped when local quality/source confidence permits.
- Question-level repair exists for localized issues.
- Concurrent organization tasks are now allowed up to 10.

Remaining bottlenecks:

- Source understanding still sends large cleaned transcript excerpts downstream.
- `parent_planner`, `writer`, evaluator, and repair all depend on model availability.
- If source brief is weak, downstream prompts become longer and less certain.

Fix direction:

- Cache transcript, parsed document text, `LessonSourcePack`, and generated plan by source hash plus generation settings hash.
- Make fast path:

```text
deterministic parse
-> one source-pack extraction or deterministic pack
-> one writer call
-> deterministic validator
```

- Make high-quality path:

```text
fast path
-> evaluator only when needed
-> targeted repair only for failed fields/questions
```

Acceptance:

- Fast path uses no more than 2 model calls after ASR.
- High-quality path uses no more than 3 model calls after ASR.
- No full-plan rewrite for one wrong choice answer.

### P1: New Generation And Regeneration Can Diverge

Current state:

- Regeneration creates a new version and can reuse current version source artifacts.
- It still reruns with current prompts, current runtime config, and possibly different options.
- Nonzero temperatures and fallback paths mean outputs can differ.

Correct product definition:

- New generation: ingest source, build source pack, generate version.
- Regeneration: reuse the selected version's source pack and explicit generation settings unless the user changes them.
- Re-render: no model call; same canonical JSON, new renderer output only.

Acceptance:

- `重新生成` and `新建生成` are not expected to be byte-identical, but they must obey the same source pack, constraints, question-count contract, and renderer contract.
- A `重新渲染PDF` operation must not change generated content.

## Target Architecture

### 1. LessonSourcePack

All inputs become one structure:

```json
{
  "source_id": "sha256:...",
  "source_type": "text|pdf|pptx|docx|audio_transcript",
  "title": "勾股数、特殊角度αβ与和角推导",
  "language": "zh",
  "segments": [
    {
      "id": "seg-001",
      "heading": "整数勾股数",
      "text": "...",
      "start_offset": 0,
      "end_offset": 120,
      "speaker": "teacher",
      "confidence": 0.88
    }
  ],
  "detected_topics": [],
  "math_blocks": [],
  "teacher_actions": [],
  "warnings": []
}
```

Audio rule:

```text
audio upload
-> shared ASR
-> transcript cache
-> optional transcript polish
-> LessonSourcePack
```

Audio must not go directly into the plan generator.

### 2. lesson_review_plan_v1

The model generates only this JSON:

```json
{
  "schema_version": "lesson_review_plan_v1",
  "document_title": "",
  "audience": {"subject": "", "grade": ""},
  "lesson_summary": "",
  "knowledge_map": [],
  "review_schedule": [],
  "practice_tasks": [],
  "self_check_questions": [],
  "math_blocks": [],
  "teacher_checkpoints": [],
  "uncertainties": [],
  "source_coverage": []
}
```

The LLM does not generate CSS, HTML, PDF layout, or DOCX layout.

### 3. Formula Contract

Formulas should not be uncontrolled inline text.

```text
正文引用: 牛顿第二定律可以写作 {{math:newton_second_law}}。
结构保存: {"id": "newton_second_law", "latex": "F = ma", "display": true}
```

Preview uses KaTeX or MathJax. DOCX should use Pandoc or an OMML conversion path. If DOCX formula perfection is deferred, DOCX keeps readable LaTeX while preview/PDF remain correct.

### 4. Validator Before Evaluator

Validator checks:

- document title exists
- review days match generation options exactly
- visible printable question count matches parsed teacher constraints
- every practice task has action, answer, and expected output
- every self-check question has answer/explanation
- every math placeholder has a math block
- every math block referenced by content exists
- source coverage references existing segments
- renderer can produce preview/PDF without dropping content

Evaluator checks:

- task sequence is educationally useful
- student workload is reasonable
- generated questions cover key ideas
- weak source assumptions are clearly marked
- plan is not just a summary

Only one bounded repair should run by default.

## Open-Source Strategy

Use mature ideas, not whole platforms.

- Claw-ED: reuse the pattern of a structured middle object and quality gates. Do not import the whole CLI/local teaching package architecture.
- Skill-Anything: reuse section-aware parsing, map-reduce, cache, concurrency, and fast/smart model routing for long transcripts and documents.
- Open Notebook: reuse the product shape of source upload plus fixed transformations. Do not adopt its whole runtime if current workflow is sufficient.
- faster-whisper / WhisperX: keep faster-whisper as fallback; evaluate WhisperX only when speaker diarization and word timestamps become first-class needs.
- MarkItDown / Docling / MinerU: keep MarkItDown for simple Office/PDF; evaluate Docling or MinerU for complex PDFs, formula extraction, OCR, tables, and reading order.
- Instructor / PydanticAI: use for schema-constrained generation and retry around `lesson_review_plan_v1`; Instructor is likely lighter if the need is only structured JSON.
- KaTeX / Pandoc: KaTeX for preview; Pandoc for DOCX with math when formula export becomes a first-class requirement.

Avoid:

- Full LangChain/Haystack migration for this feature.
- Multi-agent writer/reviewer/researcher loops as the default.
- Letting the model write final document layout.

## Target Metrics

Track these per generation:

- source pack confidence
- source pack segment count
- source coverage ratio
- model call count
- wall-clock latency by stage
- validator pass/fail category
- evaluator pass/fail category
- repair count
- visible question count
- answer-key count
- PDF renderer dropped-count
- teacher constraint compliance
- successful version rate

## Regression Fixtures

Add these to evals:

- `lesson-100-pythagorean-alpha-beta-one-day-10q`
- `low-evidence-text-only-math`
- `task_blocks-printable-questions`
- `sections.questions-printable-questions`
- `choice-answer-wrong-math-repair`
- `pdf-choice-count-no-truncation`
- `same-source-regeneration-contract`

## Final Judgment

The current implementation has the right direction: source brief, bounded quality policy, question repair, versioning, and async tasks are valuable.

The next step should not be more prompt wording. The next step is to lock the product contract:

```text
same source + same constraints
-> same canonical structure requirements
-> same validator result
-> same visible renderer result
```

That is the difference between a good demo and a reliable teacher-facing workflow.
