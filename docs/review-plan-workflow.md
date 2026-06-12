# Review Plan Workflow Audit and Architecture

## Workflow Audit

### Current Entry Points

- Frontend: `frontend/src/App.tsx` posts text and file payloads to `/api/review-plans`.
- Backend API: `app.py` creates a pending lesson and returns `202`.
- Worker: `app.py::_run_review_plan_generation_job` handles transcription, plan generation, PDF rendering, and final status.
- LLM client: `review_plan_workflow.llm.client.generate_review_plan_json()`.
- Prompt source: `review_plan_workflow/prompts/` registry plus subject packs, style config, and rubrics.
- Renderer: `review_plan_templates.single_lesson_pdf` adapts the plan into `review_plan_templates.generate_review_pdfs`.

### Current Generation Flow

1. The frontend collects subject, class, topic, lesson date, weak points, and text/file input.
2. `/api/review-plans` validates auth, class access, duplicate request identity, and credits.
3. The backend creates a pending lesson and starts a background worker.
4. The worker optionally transcribes audio, then calls `review_plan_workflow.service`.
5. The workflow runs deterministic intake/source/scope/time/task/prompt-bundle nodes.
6. The workflow-native `plan_generator` makes one structured JSON LLM call.
7. The deterministic quality gate records schema/quality review and revision warnings.
8. The PDF adapter maps the returned JSON into the ReportLab review-plan template.
9. The lesson row stores final `plan_json`, `pdf_path`, status, error fields, and run trace metadata.

### Single API / Workflow Assessment

The product entry is asynchronous. Generation now has persisted node outputs and trace metadata, but the final student-facing plan is still produced by one LLM plan-generation node. The next boundary to remove is metadata-only revision.

### Controls And Remaining Gaps

- Schema validation: final plan and node context now have Pydantic boundaries; node-level repair retry is still pending.
- Intermediate state: node outputs are now persisted in `review_plan_runs`; node replay is still pending.
- Retry and revision: existing retry behavior is task-level, not schema-level or quality-level.
- Quality gate: deterministic quality review now exists; LLM revision is still pending.
- Trace: review-plan traceId, node logs, prompt version, style version, and schema version now exist.
- Eval: existing tests cover async API and PDF basics, but not subject quality fixtures.
- Style separation: PDF style values were hard-coded in the renderer.
- Subject separation: math, physics, and IELTS rules were not represented as repo-managed subject packs.

## Code Structure Audit

| File | Lines | Current Responsibilities | Risk | Recommendation |
|---|---:|---|---|---|
| `lesson_manager.py` | 12000+ | DB schema, accounts, classes, lessons, students, CLI | Too large to split safely in this pass | Add only focused review-plan run helpers now |
| `frontend/src/App.tsx` | 10000+ | Whole app UI and review-plan page | Too many UI responsibilities | Keep frontend as API caller only in this phase |
| `app.py` | 7000+ | Routes, workers, AI charge orchestration | Review-plan worker owns too much generation detail | Move plan generation orchestration into `review_plan_workflow.service` |
| `ai_processor.py` | 2400+ | AI clients, prompts, legacy plan generation, other AI features | Giant inline prompt and unrelated AI features remain coupled | Do not use it from the review-plan workflow path; keep only for historical direct callers until a later cleanup |
| `generate_review_pdfs.py` | 1600+ | PDF rendering and visual style | Style hard-coded in Python | Load unified style config with physics as master visual language |

## Framework Decision

### Current Need

- Fixed pipeline or open-ended agent: fixed pipeline.
- Persistent graph state: not needed in Phase 1.
- Human-in-the-loop: not needed now.
- Branch recovery: task recovery is enough; node checkpoint replay can wait.
- Dynamic tool use: not needed.
- Long-running state: not needed for single-lesson generation.

### Recommendation

Use the existing OpenAI-compatible SDK, Pydantic schemas, a lightweight workflow executor, prompt registry, subject packs, unified style config, deterministic quality gate, trace logging, and eval fixtures.

### Why Not LangChain / LangGraph in Phase 1

The review-plan flow has a known order and should be controlled by code. Code should decide schema validity, score thresholds, revision limits, and node order. LangGraph becomes appropriate only when the product needs teacher approvals at intermediate nodes, pause/resume, tool-heavy retrieval, complex branching, graph visualization, or node-level replay.

## New Architecture

`review_plan_workflow/` is the new boundary:

- `executor.py`: small node runner with logs and node outputs.
- `state.py`: traceId, versions, warnings, logs, and node outputs.
- `schemas.py`: Pydantic schemas for inputs, node outputs, quality review, and final plan.
- `service.py`: single-lesson workflow entry used by the Flask worker.
- `nodes/`: intake normalizer, subject router, source analyzer, scope planner, time allocator, task blueprint, prompt bundle builder, native plan generator, and revision boundary.
- `llm/`: prompt registry, renderer, JSON parsing, OpenAI-compatible chat client, and usage extraction.
- `prompts/subjects/`: common, math, physics, IELTS subject packs.
- `prompts/styles/review_plan_style.yaml`: one unified visual system using physics as the master style.
- `prompts/rubrics/`: quality and workload checks.
- `evals/fixtures/`: minimum subject regression cases.

## Prompt Layering

Final prompt composition must follow this order:

1. System role prompt.
2. Node task prompt.
3. Subject pack.
4. Relevant schema description.
5. Current workflow state.
6. Style config only in final rendering/PDF rendering.
7. Rubric only in quality/revision nodes.

Do not reassemble the teacher prompt files into one super prompt.

## Trace and Debugging

Each generation run receives a `trace_id`. The `review_plan_runs` table stores:

- lesson and organization IDs
- status
- subject
- provider/model
- prompt/schema/style versions
- warnings
- quality review
- node outputs
- node logs

API responses may include `trace_id`, `workflow_warnings`, `quality_review`, `prompt_version`, and `style_version` without breaking older frontend consumers.

## Current Node Chain

The current single-lesson service executes this ordered chain:

1. `intake_normalizer`: normalize raw request fields and missing info.
2. `subject_router`: choose math, physics, IELTS, or common subject pack.
3. `source_analyzer`: extract confirmed topics, evidence, and source risks.
4. `scope_planner`: build review days, module sequence, review loop, warnings, and assumptions.
5. `time_allocator`: map the review scope to day-level workload and buffer strategy.
6. `task_blueprint`: produce subject-aware task blocks, required components, output contract, and risk controls.
7. `prompt_bundle_builder`: render the next LLM prompt bundle and version it.
8. `plan_generator`: calls the workflow-native OpenAI-compatible JSON generator using the rendered prompt bundle.
9. `quality_reviewer`: deterministic schema and quality gate.
10. `revision_policy`: records revision-required warnings until the dedicated revision node is implemented.

## Adding a New Subject

1. Add `prompts/subjects/<subject>.yaml`.
2. Add subject-specific checks to `prompts/rubrics/subject-specific-checks.yaml`.
3. Add at least one eval fixture.
4. Update the subject router mapping.
5. Add quality-gate checks only when they can be expressed deterministically.

## Running Evals

Phase 1 eval fixtures are JSON files under `review_plan_workflow/evals/fixtures/`. They are not a full benchmark suite yet; they are a regression checklist for schema, subject fit, workload sanity, and factuality.

## Known Limitations

- Plan generation no longer calls `ai_processor.parse_and_generate_plan()`, but it is still a single LLM plan-generation node after structured intake/source/scope/time/task/prompt-bundle preparation.
- Revision is still recorded as metadata; a dedicated LLM revision node is the next cleanup target.
- IELTS source material currently covers Reading best; full four-skill IELTS generation remains Phase 2.
