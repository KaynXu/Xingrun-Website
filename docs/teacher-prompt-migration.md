# Teacher Prompt Migration

## Purpose

Teacher prompts must be decomposed into maintainable workflow assets. Do not paste teacher prompts directly into the system prompt, and do not concatenate math, physics, and IELTS instructions into one giant prompt.

## Source Files

Current source material:

- `/Users/xiaodi/Desktop/星润复习计划工作流/物理.md`
- `/Users/xiaodi/Desktop/星润复习计划工作流/雅思.md`
- `/Users/xiaodi/Desktop/星润复习计划工作流/数学/崔老师.md`
- `/Users/xiaodi/Desktop/星润复习计划工作流/数学/华老师.md`
- `/Users/xiaodi/Desktop/星润复习计划工作流/数学/崔老师.py`

These files are inputs to migration. Runtime code must not depend on the desktop path.

## Decomposition Template

For each teacher prompt, record:

- Source prompt: file, subject, author/version.
- Extracted role rules.
- Extracted subject rules.
- Extracted planning logic.
- Extracted output style.
- Extracted quality criteria.
- Valuable parts to keep.
- Conflicts.
- Parts to remove.
- Migration target: system prompt, node prompt, subject pack, style, rubric, schema.

## Math Merge Strategy

Maintain one `math.yaml`, not two long-term math prompts.

- Keep 崔老师 version for concrete题目质量、公式表达、口述卡片、出品前检查.
- Keep 华老师 version for stable 5-day structure, full-lesson coverage, quote replay, and pagination rules.
- Move visual/page rules into style config, not the subject pack.
- Move quality rules into rubrics.
- Move output shape into schemas.
- Remove duplicate expressions and resolve conflicts explicitly.

## Physics Migration Strategy

Physics provides the master visual language for all subjects:

- Logo palette, light background, card rhythm, answer-page plain background, core formula cards, and visual safety rules move into `prompts/styles/review_plan_style.yaml`.
- Physics-specific content remains in `prompts/subjects/physics.yaml`.
- Formula/unit/experiment/graph requirements belong in subject pack and rubric.
- Scientist stories and background assets are style/component capabilities, not a separate physics-only renderer.

## IELTS Migration Strategy

The current IELTS source mainly covers IELTS Reading. Migrate it honestly:

- Reading rules enter `prompts/subjects/ielts.yaml`.
- Four-skill IELTS planning remains an explicit Phase 2 extension.
- Band descriptor, feedback loop, rewrite/retell, and mock cycle requirements enter subject pack and rubrics.
- Do not pretend the current Reading prompt already covers Listening, Writing, and Speaking completely.

## Conflict Handling

When prompts disagree:

- Product workflow rules win over historical local path rules.
- Unified style config wins over subject-local visual style.
- Schema wins over free-form output examples.
- Rubric wins over vague quality preferences.
- If math and physics disagree on 5-day coverage, preserve each subject's planning rule in subject pack while keeping the same PDF style system.

## Regression Testing

Every migrated rule should map to one of:

- A schema assertion.
- A deterministic quality-gate check.
- A subject fixture expected criterion.
- A PDF layout/style smoke test.
- A documented manual visual check when automation is not realistic yet.
