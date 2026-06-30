# Review Plan Generation Options Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real per-version review plan generation options so teachers can choose standard, compressed, daily, or custom review schedules and pass one-off teacher requirements into the LLM chain.

**Architecture:** Store normalized `generation_options` on each `review_plan_versions` row and pass that same normalized object through API serializers, async workers, workflow input, prompts, revision, quality gate, PDF rendering checks, and frontend create/regenerate UI. Old versions without saved options fall back to the existing standard five-day schedule. The UI stays one-step for new generation and replaces regenerate confirmation with a settings dialog.

**Tech Stack:** Python 3, Flask, SQLite, Pydantic, unittest/pytest, Vite, React, TypeScript, node:test, lucide-react.

## Global Constraints

- Source spec: `docs/superpowers/specs/2026-06-30-review-plan-generation-options-design.md`.
- Before implementation, fetch remote metadata, confirm local `develop` matches `origin/develop`, and create the implementation branch from `develop`.
- Default schedule for missing options is `standard` with `review_days=[1,2,7,14,30]`.
- First version supports `standard`, `compressed`, `daily`, and `custom` schedule modes.
- Custom and daily schedules are capped at 30 review days.
- Teacher one-off requirements are version-scoped, not saved as reusable templates.
- Teacher requirements can influence generation but cannot override printable structure, factuality, schema, or quality gate requirements.
- Regeneration must create a new version and must not overwrite the previous ready PDF.
- Keep old version rows compatible when `generation_options_json` is absent or empty.
- Do not include runtime data files, local DBs, PDFs, uploads, or generated output folders in commits.

---

## Source Spec

- `docs/superpowers/specs/2026-06-30-review-plan-generation-options-design.md`

## File Structure

- Create `review_plan_workflow/generation_options.py`
  - Owns normalization, validation, summary labels, and trace-safe previews.
  - Used by backend storage, API, workflow input, tests, and frontend-facing serializers.

- Modify `lesson_manager.py`
  - Add `generation_options_json` schema migration.
  - Serialize normalized `generation_options` from version rows.
  - Store options in `create_review_plan_version()`.
  - Preserve options through legacy compatibility helpers and active version projections.

- Modify `app.py`
  - Parse `generation_options` from JSON and multipart requests.
  - Pass normalized options into version creation and async workers.
  - Include `generation_options` and `generation_summary` in list/detail/version serializers.
  - Regenerate with request options, then current version options, then standard fallback.

- Modify `review_plan_workflow/schemas.py`
  - Add schedule fields to `ReviewPlanInput`.
  - Remove fixed day validators from `AgenticDayStrategy` and `ReviewPlanDay`.
  - Validate positive day integers but not fixed day membership.

- Modify workflow nodes:
  - `review_plan_workflow/service.py`
  - `review_plan_workflow/state.py`
  - `review_plan_workflow/nodes/scope_planner.py`
  - `review_plan_workflow/nodes/time_allocator.py`
  - `review_plan_workflow/nodes/prompt_bundle_builder.py`
  - `review_plan_workflow/nodes/plan_generator.py`
  - `review_plan_workflow/nodes/revision.py`

- Modify prompt files:
  - `review_plan_workflow/prompts/nodes/task-generator.md`
  - `review_plan_workflow/prompts/nodes/revision.md`
  - `review_plan_workflow/prompts/rubrics/review-plan-quality.yaml`

- Modify `review_plan_workflow/quality_gate.py`
  - Accept required review days and schedule mode.
  - Replace fixed five-day check with required-day check.
  - Add compressed one-day density guard.

- Modify `review_plan_workflow/observability.py`
  - Include trace-safe schedule mode and review days in review input summaries.

- Modify `review_plan_templates/single_lesson_pdf.py`
  - Preserve custom/compressed/daily labels from generated days where available.
  - Smoke-test compressed one-day rendering.

- Modify eval fixtures:
  - Keep existing fixed-day fixtures explicitly standard.
  - Add at least one compressed or custom schedule fixture when workflow evals are run.

- Modify frontend files:
  - `frontend/src/features/review-generation/LessonInput.tsx`
  - `frontend/src/features/review-generation/ReviewGenerationPage.tsx`
  - `frontend/src/features/review-generation/ReviewPlanDetailView.tsx`
  - `frontend/src/features/review-generation/reviewPlanVersions.ts`
  - `frontend/src/reviewGenerationAsync.ts`

- Modify tests:
  - `tests/test_review_plan_generation_options.py`
  - `tests/test_review_plan_async_api.py`
  - `tests/test_review_plan_async_store.py`
  - `tests/test_review_plan_workflow.py`
  - `frontend/src/reviewGenerationAsync.test.ts`
  - `frontend/src/review-generation-async.test.tsx`

- Modify `handoff.md`
  - Record implementation proof and remaining deploy status after verification.

## Task 0: Branch Freshness And Implementation Branch

**Files:**
- None

- [ ] **Step 1: Fetch and confirm develop freshness**

Run:

```bash
git fetch origin develop --prune
git switch develop
git pull --ff-only origin develop
git rev-list --left-right --count develop...origin/develop
```

Expected: `0	0`.

- [ ] **Step 2: Create implementation branch**

Run:

```bash
git switch -c codex/review-plan-generation-options
```

Expected: implementation branch starts from current `develop`.

## Task 1: Backend Generation Options Normalizer And Storage

**Files:**
- Create: `review_plan_workflow/generation_options.py`
- Create: `tests/test_review_plan_generation_options.py`
- Modify: `lesson_manager.py`
- Modify: `tests/test_review_plan_async_store.py`

**Interfaces:**
- Produces: `normalize_generation_options(value: object | None, *, source: str = "create") -> dict[str, object]`
- Produces: `generation_options_summary(options: Mapping[str, object]) -> str`
- Produces: `generation_options_trace_summary(options: Mapping[str, object]) -> dict[str, object]`
- Consumes later: `create_review_plan_version(..., generation_options: Optional[dict[str, object]] = None, generation_options_source: str = "create")`
- Produces: `update_review_plan_version_generation_options(version_id: int, generation_options: object | None) -> None`

- [ ] **Step 1: Write normalizer tests**

Create `tests/test_review_plan_generation_options.py` with tests that define the exact contract:

```python
import unittest

from review_plan_workflow.generation_options import (
    generation_options_summary,
    generation_options_trace_summary,
    normalize_generation_options,
)


class ReviewPlanGenerationOptionsTestCase(unittest.TestCase):
    def test_defaults_to_standard_five_day_schedule(self):
        options = normalize_generation_options(None)
        self.assertEqual(options["schedule_mode"], "standard")
        self.assertEqual(options["review_days"], [1, 2, 7, 14, 30])
        self.assertEqual(options["daily_count"], None)
        self.assertEqual(options["user_requirements"], "")
        self.assertEqual(options["source"], "create")
        self.assertEqual(generation_options_summary(options), "标准 5 次")

    def test_compressed_forces_single_day(self):
        options = normalize_generation_options(
            {"schedule_mode": "compressed", "review_days": [1, 2, 7], "user_requirements": "明天考试前冲刺"},
            source="regenerate",
        )
        self.assertEqual(options["schedule_mode"], "compressed")
        self.assertEqual(options["review_days"], [1])
        self.assertEqual(options["daily_count"], 1)
        self.assertEqual(options["user_requirements"], "明天考试前冲刺")
        self.assertEqual(options["source"], "regenerate")
        self.assertEqual(generation_options_summary(options), "压缩 1 天")

    def test_daily_count_expands_to_consecutive_days(self):
        options = normalize_generation_options({"schedule_mode": "daily", "daily_count": 4})
        self.assertEqual(options["review_days"], [1, 2, 3, 4])
        self.assertEqual(options["daily_count"], 4)
        self.assertEqual(generation_options_summary(options), "连续 4 天")

    def test_custom_accepts_comma_string_sorts_and_dedupes(self):
        options = normalize_generation_options({"schedule_mode": "custom", "review_days": "7, 1, 3, 3"})
        self.assertEqual(options["review_days"], [1, 3, 7])
        self.assertEqual(options["daily_count"], None)
        self.assertEqual(generation_options_summary(options), "自定义 1,3,7")

    def test_rejects_zero_negative_and_more_than_30_days(self):
        for payload in (
            {"schedule_mode": "custom", "review_days": [0]},
            {"schedule_mode": "custom", "review_days": [-1]},
            {"schedule_mode": "custom", "review_days": [True]},
            {"schedule_mode": "custom", "review_days": [1.5]},
            {"schedule_mode": "daily", "daily_count": 31},
            {"schedule_mode": "daily", "daily_count": "1,2,3"},
            {"schedule_mode": "custom", "review_days": list(range(1, 32))},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    normalize_generation_options(payload)

    def test_trace_summary_does_not_expose_full_requirement_text(self):
        options = normalize_generation_options({
            "schedule_mode": "standard",
            "user_requirements": "题量少一点，适合明天考试前冲刺，多给选择题诊断",
        })
        trace = generation_options_trace_summary(options)
        self.assertEqual(trace["schedule_mode"], "standard")
        self.assertEqual(trace["review_days"], [1, 2, 7, 14, 30])
        self.assertEqual(trace["has_user_requirements"], True)
        self.assertIn("user_requirements_preview", trace)
        self.assertLessEqual(len(trace["user_requirements_preview"]), 40)
```

- [ ] **Step 2: Run the normalizer tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_generation_options -v
```

Expected: fail with `ModuleNotFoundError` for `review_plan_workflow.generation_options`.

- [ ] **Step 3: Implement `generation_options.py`**

Create `review_plan_workflow/generation_options.py` with these public functions:

```python
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


STANDARD_REVIEW_DAYS = [1, 2, 7, 14, 30]
SUPPORTED_SCHEDULE_MODES = {"standard", "compressed", "daily", "custom"}
MAX_REVIEW_DAYS = 30
MAX_USER_REQUIREMENTS_CHARS = 1000


def _coerce_mapping(value: object | None) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("generation_options must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("generation_options must be an object")
        return dict(parsed)
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError("generation_options must be an object")


def _parse_day_values(value: object) -> list[int]:
    raw_values: list[object]
    if isinstance(value, str):
        raw_values = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple)):
        raw_values = list(value)
    else:
        raw_values = [value]
    days: list[int] = []
    for raw in raw_values:
        if raw in ("", None):
            continue
        if isinstance(raw, bool):
            raise ValueError("review_days must contain positive integers")
        try:
            day = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("review_days must contain positive integers") from exc
        if isinstance(raw, float) and not raw.is_integer():
            raise ValueError("review_days must contain positive integers")
        if day <= 0:
            raise ValueError("review_days must contain positive integers")
        days.append(day)
    days = sorted(set(days))
    if not days:
        raise ValueError("review_days must include at least one day")
    if len(days) > MAX_REVIEW_DAYS or max(days) > MAX_REVIEW_DAYS:
        raise ValueError(f"review_days cannot exceed day {MAX_REVIEW_DAYS}")
    return days


def _clean_user_requirements(value: object) -> str:
    text = str(value or "").strip()
    return text[:MAX_USER_REQUIREMENTS_CHARS]


def normalize_generation_options(value: object | None, *, source: str = "create") -> dict[str, object]:
    data = _coerce_mapping(value)
    mode = str(data.get("schedule_mode") or "standard").strip().lower()
    if mode not in SUPPORTED_SCHEDULE_MODES:
        raise ValueError("schedule_mode must be standard, compressed, daily, or custom")

    daily_count: int | None = None
    if mode == "standard":
        review_days = list(STANDARD_REVIEW_DAYS)
    elif mode == "compressed":
        review_days = [1]
        daily_count = 1
    elif mode == "daily":
        try:
            if isinstance(data.get("daily_count"), str) and "," in data.get("daily_count", ""):
                raise ValueError("daily_count must be a positive integer")
            daily_count = int(data.get("daily_count") or len(data.get("review_days") or []))
        except (TypeError, ValueError) as exc:
            raise ValueError("daily_count must be a positive integer") from exc
        if daily_count <= 0 or daily_count > MAX_REVIEW_DAYS:
            raise ValueError(f"daily_count must be between 1 and {MAX_REVIEW_DAYS}")
        review_days = list(range(1, daily_count + 1))
    else:
        review_days = _parse_day_values(data.get("review_days"))

    return {
        "schedule_mode": mode,
        "review_days": review_days,
        "daily_count": daily_count,
        "user_requirements": _clean_user_requirements(data.get("user_requirements")),
        "source": str(source or data.get("source") or "create").strip() or "create",
    }


def generation_options_summary(options: Mapping[str, object]) -> str:
    mode = str(options.get("schedule_mode") or "standard")
    days = [int(day) for day in options.get("review_days") or STANDARD_REVIEW_DAYS]
    if mode == "compressed":
        return "压缩 1 天"
    if mode == "daily":
        return f"连续 {len(days)} 天"
    if mode == "custom":
        return "自定义 " + ",".join(str(day) for day in days)
    return "标准 5 次"


def generation_options_trace_summary(options: Mapping[str, object]) -> dict[str, object]:
    requirements = str(options.get("user_requirements") or "").strip()
    summary = {
        "schedule_mode": str(options.get("schedule_mode") or "standard"),
        "review_days": [int(day) for day in options.get("review_days") or STANDARD_REVIEW_DAYS],
        "has_user_requirements": bool(requirements),
    }
    if requirements:
        summary["user_requirements_preview"] = requirements[:40]
    return summary
```

- [ ] **Step 4: Add version storage tests**

In `tests/test_review_plan_async_store.py`, add a test near existing version helper tests:

```python
    def test_create_review_plan_version_stores_generation_options(self):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-30",
            subject="数学",
            grade="",
            topic="分式方程",
            summary="课堂总结",
            weak_points="",
            class_id=0,
            created_by_user_id=7,
        )

        version = lesson_manager.create_review_plan_version(
            lesson_id=lesson_id,
            status="generating",
            generation_options={"schedule_mode": "compressed", "user_requirements": "题量少一点"},
        )

        self.assertEqual(version["generation_options"]["schedule_mode"], "compressed")
        self.assertEqual(version["generation_options"]["review_days"], [1])
        self.assertEqual(version["generation_options"]["source"], "create")
        self.assertEqual(version["generation_summary"], "压缩 1 天")
```

- [ ] **Step 5: Run storage tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_generation_options tests.test_review_plan_async_store -v
```

Expected: normalizer tests pass after Step 3; store test fails because `create_review_plan_version()` does not accept `generation_options`.

- [ ] **Step 6: Update `lesson_manager.py` schema and serializers**

Add imports near existing imports:

```python
from review_plan_workflow.generation_options import (
    generation_options_summary,
    normalize_generation_options,
)
```

In `_ensure_review_plan_versions_schema()`, add:

```python
_ensure_column(conn, "review_plan_versions", "generation_options_json", "TEXT NOT NULL DEFAULT ''")
```

In rebuild/copy code for `review_plan_versions`, include `generation_options_json` with fallback `''` wherever columns are copied.

In `_review_plan_version_from_row()`, add:

```python
    try:
        raw_generation_options = version.get("generation_options_json") or None
        generation_options_source = "create"
        if raw_generation_options:
            parsed_generation_options = json.loads(raw_generation_options)
            if isinstance(parsed_generation_options, dict):
                generation_options_source = str(parsed_generation_options.get("source") or "create")
        generation_options = normalize_generation_options(raw_generation_options, source=generation_options_source)
    except ValueError:
        generation_options = normalize_generation_options(None)
    except json.JSONDecodeError:
        generation_options = normalize_generation_options(None)
    version["generation_options"] = generation_options
    version["generation_summary"] = generation_options_summary(generation_options)
```

Add helper:

```python
def _dump_generation_options(value: object | None, *, source: str = "create") -> str:
    try:
        return json.dumps(normalize_generation_options(value, source=source), ensure_ascii=False)
    except ValueError:
        raise
```

Update `create_review_plan_version()` signature and insert SQL:

```python
def create_review_plan_version(
    ...,
    generation_options: Optional[dict[str, object]] = None,
    generation_options_source: str = "create",
) -> dict:
    ...
    generation_options_json = _dump_generation_options(generation_options, source=generation_options_source)
    ...
    INSERT INTO review_plan_versions (..., same_lesson_materials_json, generation_options_json)
    VALUES (..., ?, ?)
```

Add public helper for regenerate tests and manual backfills:

```python
def update_review_plan_version_generation_options(version_id: int, generation_options: object | None) -> None:
    generation_options_json = _dump_generation_options(generation_options, source="regenerate")
    with get_conn() as conn:
        conn.execute(
            "UPDATE review_plan_versions SET generation_options_json = ? WHERE id = ?",
            (generation_options_json, int(version_id)),
        )
```

- [ ] **Step 7: Run Task 1 tests**

Run:

```bash
python3 -m unittest tests.test_review_plan_generation_options tests.test_review_plan_async_store -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 1**

Run:

```bash
git add review_plan_workflow/generation_options.py lesson_manager.py tests/test_review_plan_generation_options.py tests/test_review_plan_async_store.py
git commit -m "feat: store review plan generation options"
```

## Task 2: API Parsing, Regenerate Fallback, And Serialization

**Files:**
- Modify: `app.py`
- Modify: `tests/test_review_plan_async_api.py`

**Interfaces:**
- Consumes: `normalize_generation_options()` from Task 1.
- Produces: JSON and multipart create support for `generation_options`.
- Produces: regenerate fallback order: request options, current version options, standard default.

- [ ] **Step 1: Add API tests for create and regenerate options**

In `tests/test_review_plan_async_api.py`, add focused tests near existing review plan create/regenerate tests:

```python
    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_create_review_plan_accepts_generation_options(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        response = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            json={
                "subject": "数学",
                "topic": "分式方程",
                "date": "2026-06-30",
                "summary_text": "课堂讲了分式方程去分母和验根。",
                "input_type": "text",
                "generation_options": {
                    "schedule_mode": "compressed",
                    "user_requirements": "明天考试前冲刺",
                },
            },
        )
        self.assertEqual(response.status_code, 202)
        lesson_id = response.get_json()["id"]
        version = lesson_manager.list_review_plan_versions(lesson_id)[0]
        self.assertEqual(version["generation_options"]["schedule_mode"], "compressed")
        self.assertEqual(version["generation_options"]["review_days"], [1])
        self.assertEqual(mock_start_thread.call_args.kwargs["generation_options"]["review_days"], [1])

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_text_file_review_plan_accepts_generation_options_json_string(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        response = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            data={
                "input_type": "file",
                "subject": "数学",
                "topic": "分式方程",
                "generation_options": '{"schedule_mode":"custom","review_days":[1,3,7]}',
                "upload_file": (
                    io.BytesIO("课堂讲了分式方程去分母和验根。".encode("utf-8")),
                    "lesson.txt",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(mock_start_thread.call_args.kwargs["generation_options"]["review_days"], [1, 3, 7])

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_regenerate_prefills_current_version_options_when_request_omits_them(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-30",
            subject="数学",
            grade="",
            topic="分式方程",
            summary="课堂讲了分式方程去分母和验根。",
            weak_points="",
            created_by_user_id=1,
        )
        current = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(
            current["id"],
            plan={"lesson_info": {"topic": "旧计划"}, "days": []},
            pdf_path="/tmp/old-review.pdf",
        )
        lesson_manager.update_review_plan_version_generation_options(
            current["id"],
            {"schedule_mode": "custom", "review_days": [1, 3, 7], "user_requirements": "题量少一点"},
        )
        response = self.client.post(
            f"/api/review-plans/{lesson_id}/regenerate",
            headers=self._auth_headers(self.owner_token),
            json={},
        )
        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertEqual(payload["generation_options"]["review_days"], [1, 3, 7])
        self.assertEqual(payload["generation_options"]["source"], "regenerate")
        self.assertEqual(mock_start_thread.call_args.kwargs["generation_options"]["review_days"], [1, 3, 7])
        self.assertEqual(mock_start_thread.call_args.kwargs["generation_options"]["source"], "regenerate")

    @patch("app._start_review_plan_generation_thread")
    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_regenerate_allows_overriding_previous_generation_options(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
        mock_start_thread,
    ):
        lesson_id = lesson_manager.create_pending_lesson(
            date_str="2026-06-30",
            subject="数学",
            grade="",
            topic="分式方程",
            summary="课堂讲了分式方程去分母和验根。",
            weak_points="",
            created_by_user_id=1,
        )
        current = lesson_manager.create_review_plan_version(lesson_id=lesson_id, status="generating")
        lesson_manager.complete_review_plan_version(
            current["id"],
            plan={"lesson_info": {"topic": "旧计划"}, "days": []},
            pdf_path="/tmp/old-review.pdf",
        )
        response = self.client.post(
            f"/api/review-plans/{lesson_id}/regenerate",
            headers=self._auth_headers(self.owner_token),
            json={"generation_options": {"schedule_mode": "daily", "daily_count": 3}},
        )
        self.assertEqual(response.status_code, 202)
        payload = response.get_json()
        self.assertEqual(payload["generation_options"]["review_days"], [1, 2, 3])
        self.assertEqual(payload["generation_options"]["source"], "regenerate")
        self.assertEqual(mock_start_thread.call_args.kwargs["generation_options"]["review_days"], [1, 2, 3])
        self.assertEqual(mock_start_thread.call_args.kwargs["generation_options"]["source"], "regenerate")

    @patch("app.ensure_feature_credits_available")
    @patch("app.has_review_plan_api_key", return_value=True)
    def test_invalid_generation_options_return_400(
        self,
        _mock_has_api_key,
        _mock_ensure_credits,
    ):
        response = self.client.post(
            "/api/review-plans",
            headers=self._auth_headers(self.owner_token),
            json={
                "subject": "数学",
                "summary_text": "课堂内容",
                "generation_options": {"schedule_mode": "custom", "review_days": [0]},
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("review_days", response.get_json()["error"])
```

Use the current fixture style in this file: `headers=self._auth_headers(self.owner_token)`, `lesson_manager.create_pending_lesson()`, `create_review_plan_version()`, and `complete_review_plan_version()`.

- [ ] **Step 2: Run API tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_async_api -v
```

Expected: fail on missing API parsing, response fields, or worker arguments.

- [ ] **Step 3: Add API parser helpers in `app.py`**

Near `_extract_same_lesson_materials()`, add:

```python
def _extract_generation_options(data, *, source: str) -> dict:
    raw_value = None
    if hasattr(data, "get"):
        raw_value = data.get("generation_options")
    return normalize_generation_options(raw_value, source=source)


def _generation_options_or_error(data, *, source: str):
    try:
        return _extract_generation_options(data, source=source), None
    except ValueError as exc:
        return None, (jsonify({"error": str(exc)}), 400)
```

Import:

```python
from review_plan_workflow.generation_options import normalize_generation_options
```

- [ ] **Step 4: Wire create endpoint**

In `api_lesson_create()`, after `same_lesson_materials`:

```python
    generation_options, generation_options_error = _generation_options_or_error(data, source="create")
    if generation_options_error:
        return generation_options_error
```

Pass `generation_options` into `create_review_plan_version()` and `_start_review_plan_generation_thread()`.

Return it in the `202` payload:

```python
return jsonify({
    "id": lesson_id,
    "version_id": int(version["id"]),
    "success": True,
    "status": response_status,
    "generation_options": version.get("generation_options") or generation_options,
}), 202
```

- [ ] **Step 5: Wire regenerate endpoint**

In `api_lesson_regenerate()`, parse request JSON:

```python
    data = request.get_json(silent=True) or {}
    current_version = get_current_review_plan_version(lesson_id)
    if "generation_options" in data:
        generation_options, generation_options_error = _generation_options_or_error(data, source="regenerate")
        if generation_options_error:
            return generation_options_error
    else:
        generation_options = normalize_generation_options(
            (current_version or {}).get("generation_options") or None,
            source="regenerate",
        )
```

Use `current_version` already loaded for `same_lesson_materials`. Pass `generation_options` into `create_review_plan_version(..., generation_options_source="regenerate")` and worker. Include it in response.

Update `_run_review_plan_generation_job()` and `_start_review_plan_generation_thread()` call sites to accept and forward `generation_options`. In recovery (`_recover_review_plan_generations()`), load the version row and pass `version.get("generation_options")` so service restarts do not fall back to standard days.

- [ ] **Step 6: Serialize options**

In `_serialize_review_plan_version_for_response()`, keep `generation_options`, `generation_summary`, and omit `generation_options_json`:

```python
serialized.pop("generation_options_json", None)
serialized["generation_options"] = version.get("generation_options") or normalize_generation_options(None)
serialized["generation_summary"] = version.get("generation_summary") or "标准 5 次"
```

In `_serialize_lesson_for_response()`, add current fields:

```python
serialized["generation_options"] = (current_version or {}).get("generation_options") if current_version else normalize_generation_options(None)
serialized["generation_summary"] = (current_version or {}).get("generation_summary") if current_version else "标准 5 次"
```

- [ ] **Step 7: Run API tests**

Run:

```bash
python3 -m unittest tests.test_review_plan_async_api tests.test_review_plan_generation_options -v
```

Expected: pass.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add app.py lesson_manager.py tests/test_review_plan_async_api.py
git commit -m "feat: pass generation options through review plan API"
```

## Task 3: Workflow Input, Scope, Time Allocation, And Trace Context

**Files:**
- Modify: `review_plan_workflow/schemas.py`
- Modify: `review_plan_workflow/state.py`
- Modify: `review_plan_workflow/service.py`
- Modify: `review_plan_workflow/nodes/scope_planner.py`
- Modify: `review_plan_workflow/nodes/time_allocator.py`
- Modify: `review_plan_workflow/nodes/prompt_bundle_builder.py`
- Modify: `review_plan_workflow/observability.py`
- Modify: `tests/test_review_plan_workflow.py`

**Interfaces:**
- Consumes: normalized options from API/service.
- Produces: `ReviewPlanInput.review_days`, `schedule_mode`, `user_requirements`.
- Produces: `WorkflowContext.generation_options`.

- [ ] **Step 1: Add workflow unit tests for non-standard schedules**

In `tests/test_review_plan_workflow.py`, add tests:

```python
    def test_scope_planner_uses_input_review_days(self):
        review_input = ReviewPlanInput(
            summary_text="课堂讲了分式方程去分母和验根。",
            subject="数学",
            schedule_mode="custom",
            review_days=[1, 3, 7],
        )
        normalized = NormalizedBrief(subject="math", confidence=0.9)
        route = SubjectRoute(selected_subject="math")
        source = SourceSummary(confirmed_topics=["分式方程"], confidence=0.9)
        context = WorkflowContext()

        scope = scope_planner_node.run(
            {"input": review_input, "normalized": normalized, "route": route, "source": source},
            context,
        )

        self.assertEqual(scope.review_days, [1, 3, 7])

    def test_time_allocator_labels_compressed_and_daily_modes(self):
        compressed = ReviewPlanInput(summary_text="课堂内容", schedule_mode="compressed", review_days=[1])
        daily = ReviewPlanInput(summary_text="课堂内容", schedule_mode="daily", review_days=[1, 2, 3])
        normalized = NormalizedBrief(subject="math", confidence=0.9)
        context = WorkflowContext()

        compressed_scope = ScopePlan(review_days=[1], review_loop=["全课核心复盘"])
        compressed_alloc = time_allocator_node.run(
            {"input": compressed, "normalized": normalized, "scope": compressed_scope},
            context,
        )
        self.assertEqual(compressed_alloc.review_schedule[0]["label"], "当天压缩复盘")

        daily_scope = ScopePlan(review_days=[1, 2, 3], review_loop=["定义", "例题", "错因"])
        daily_alloc = time_allocator_node.run(
            {"input": daily, "normalized": normalized, "scope": daily_scope},
            context,
        )
        self.assertEqual([item["day"] for item in daily_alloc.review_schedule], [1, 2, 3])
        self.assertIn("每日复习", daily_alloc.review_schedule[2]["label"])
```

- [ ] **Step 2: Run workflow tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow -v
```

Expected: fail because `ReviewPlanInput` lacks fields and fixed validators reject custom days.

- [ ] **Step 3: Update schemas**

In `ReviewPlanInput`, add:

```python
schedule_mode: str = "standard"
review_days: list[int] = Field(default_factory=lambda: [1, 2, 7, 14, 30])
user_requirements: str = ""

@field_validator("review_days")
@classmethod
def validate_review_days(cls, value: list[int]) -> list[int]:
    days = sorted({int(day) for day in value})
    if not days or any(day <= 0 for day in days):
        raise ValueError("review_days must contain positive integers")
    return days
```

Change `AgenticDayStrategy.validate_review_day()` and `ReviewPlanDay.validate_review_day()` to only check `value > 0`. Exact-day membership is intentionally enforced later by the quality gate with the current `ReviewPlanInput.review_days`; schema validation cannot know the chosen schedule.

- [ ] **Step 4: Update workflow context**

In `WorkflowContext`, add:

```python
generation_options: dict[str, object] = field(default_factory=dict)
```

In `generate_single_lesson_review_plan()`, add parameters:

```python
generation_options: Optional[dict[str, Any]] = None,
```

Normalize:

```python
normalized_options = normalize_generation_options(generation_options)
context.generation_options = generation_options_trace_summary(normalized_options)
review_input = ReviewPlanInput(
    ...,
    schedule_mode=str(normalized_options["schedule_mode"]),
    review_days=list(normalized_options["review_days"]),
    user_requirements=str(normalized_options.get("user_requirements") or ""),
)
context.node_outputs["generation_options"] = generation_options_trace_summary(normalized_options)
```

Update `summarize_review_input()` in `review_plan_workflow/observability.py` so Langfuse/local summaries include `schedule_mode`, `review_days`, `has_user_requirements`, and only a short requirements preview.

- [ ] **Step 5: Update scope planner**

In `scope_planner._run()`, read `review_input`:

```python
review_input = input_data["input"]
review_days = list(review_input.review_days or [1, 2, 7, 14, 30])
...
return ScopePlan(
    review_days=review_days,
    ...
)
```

Update fallback warning text from "固定间隔复习日" to "所选复习节奏".

- [ ] **Step 6: Update time allocator**

Change `_run()` to accept `input`:

```python
review_input = input_data.get("input")
mode = getattr(review_input, "schedule_mode", "standard")
```

Add label helper:

```python
def _day_label(day: int, mode: str) -> str:
    if mode == "compressed":
        return "当天压缩复盘"
    if mode == "daily":
        return f"第 {day} 天每日复习"
    if mode == "custom":
        return DAY_LABELS.get(day, f"第 {day} 天回看")
    return DAY_LABELS.get(day, f"第 {day} 天复习")
```

Update service call to pass `"input": review_input`.

- [ ] **Step 7: Include generation options in prompt variables**

In `prompt_bundle_builder._run()`, read `review_input = input_data["input"]` and add:

```python
"generation_options": {
    "schedule_mode": review_input.schedule_mode,
    "review_days": review_input.review_days,
    "user_requirements": review_input.user_requirements,
},
```

Update service call to include `"input": review_input`.

Also update `_run_parent_planner_with_fallback()` and its fallback `AgenticPlanBlueprint` in `service.py`; remove "固定 day=1,2,7,14,30" wording and generate fallback strategies from `review_input.review_days`.

- [ ] **Step 8: Run workflow tests**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow -v
```

Expected: pass.

- [ ] **Step 9: Commit Task 3**

Run:

```bash
git add review_plan_workflow/schemas.py review_plan_workflow/state.py review_plan_workflow/service.py review_plan_workflow/nodes/scope_planner.py review_plan_workflow/nodes/time_allocator.py review_plan_workflow/nodes/prompt_bundle_builder.py review_plan_workflow/observability.py tests/test_review_plan_workflow.py
git commit -m "feat: parameterize review plan schedule workflow"
```

## Task 4: Prompt, Generator Repair, Revision, And Quality Gate

**Files:**
- Modify: `review_plan_workflow/nodes/plan_generator.py`
- Modify: `review_plan_workflow/nodes/revision.py`
- Modify: `review_plan_workflow/prompts/nodes/task-generator.md`
- Modify: `review_plan_workflow/prompts/nodes/revision.md`
- Modify: `review_plan_workflow/prompts/rubrics/review-plan-quality.yaml`
- Modify: `review_plan_workflow/quality_gate.py`
- Modify: `review_plan_workflow/service.py`
- Modify: `review_plan_workflow/evals/runner.py`
- Modify: `review_plan_workflow/evals/fixtures/**/*.json`
- Modify: `review_plan_templates/single_lesson_pdf.py`
- Modify: `tests/test_review_plan_workflow.py`

**Interfaces:**
- Consumes: `ReviewPlanInput.review_days`, `schedule_mode`, `user_requirements`.
- Produces: quality gate accepts `required_review_days` and `schedule_mode`.

- [ ] **Step 1: Add quality gate tests**

In `tests/test_review_plan_workflow.py`, add:

```python
    def test_quality_gate_accepts_custom_required_days(self):
        plan = valid_single_lesson_plan(subject="数学", topic="分式方程")
        plan["days"] = [day for day in plan["days"] if day["day"] in {1, 3, 7}]
        for day in plan["days"]:
            day["blanks"] = [
                {"text": "去分母时第一步要找______。", "answer": "最简公分母"},
                {"text": "解完分式方程必须______。", "answer": "验根"},
                {"text": "增根会让原方程分母等于______。", "answer": "0"},
            ]
            day["choices"] = [
                {
                    "question": "分式方程去分母后下一步最需要检查什么？",
                    "options": ["A. 是否漏乘常数项", "B. 是否画图", "C. 是否配方", "D. 是否开平方"],
                    "answer": "A",
                },
                {
                    "question": "验根的主要目的是什么？",
                    "options": ["A. 排除增根", "B. 增加步骤", "C. 改变方程", "D. 消去未知数"],
                    "answer": "A",
                },
            ]
        review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1, 3, 7],
            schedule_mode="custom",
        )
        self.assertFalse(any("固定 5 个复习日" in issue.description for issue in review.issues))

    def test_quality_gate_flags_missing_required_custom_day(self):
        plan = valid_single_lesson_plan(subject="数学", topic="分式方程")
        plan["days"] = [day for day in plan["days"] if day["day"] in {1, 3}]
        review = review_single_lesson_plan(
            plan,
            subject="math",
            required_review_days=[1, 3, 7],
            schedule_mode="custom",
        )
        self.assertTrue(any("缺少所选复习日" in issue.description for issue in review.issues))
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow -v
```

Expected: fail because `review_single_lesson_plan()` has no required-day parameters.

- [ ] **Step 3: Parameterize quality gate**

Change signature:

```python
def review_single_lesson_plan(
    plan: dict[str, Any],
    *,
    subject: str = "",
    required_review_days: list[int] | None = None,
    schedule_mode: str = "standard",
) -> QualityReview:
```

Replace fixed set:

```python
required_days = set(required_review_days or [1, 2, 7, 14, 30])
missing_days = required_days - day_numbers
unexpected_days = day_numbers - required_days
if missing_days:
    issues.append(QualityIssue(
        severity="high",
        category="completeness",
        description="缺少所选复习日：" + ",".join(str(day) for day in sorted(missing_days)),
        suggested_fix="只输出并补齐所选 review_days 的完整数组。",
    ))
if unexpected_days:
    issues.append(QualityIssue(
        severity="medium",
        category="completeness",
        description="输出了未选择的复习日：" + ",".join(str(day) for day in sorted(unexpected_days)),
        suggested_fix="删除未在 review_days 中选择的额外复习日。",
    ))
```

For compressed plans, add after density checks:

```python
if schedule_mode == "compressed" and len(days) == 1:
    blanks_count, choices_count, bodies_count = _day_renderable_counts(days[0])
    if blanks_count < 5 and choices_count < 3:
        issues.append(QualityIssue(
            severity="high",
            category="task_actionability",
            description="压缩 1 天计划的可打印练习密度不足，无法承载全课复盘。",
            suggested_fix="单日压缩至少提供 5 个填空/口述填空或 3 道选择诊断，并覆盖全课核心错因。",
        ))
```

- [ ] **Step 4: Pass required days from service**

Change `_score_quality()` signature in `service.py`:

```python
def _score_quality(plan: dict[str, Any], *, subject: str, context: WorkflowContext, node_key: str, review_input: ReviewPlanInput) -> QualityReview:
    quality = review_single_lesson_plan(
        plan,
        subject=subject,
        required_review_days=review_input.review_days,
        schedule_mode=review_input.schedule_mode,
    )
```

Update every `_score_quality()` call, including initial local quality checks and all revision-loop checks. Do not leave a fallback path that calls `review_single_lesson_plan(plan, subject=subject)` inside the live workflow.

In eval runner, keep old default for legacy fixtures but allow fixtures to provide `generation_options`:

```python
generation_options = normalize_generation_options(fixture.get("generation_options"))
quality = review_single_lesson_plan(
    plan,
    subject=subject,
    required_review_days=list(generation_options["review_days"]),
    schedule_mode=str(generation_options["schedule_mode"]),
)
```

Keep existing fixtures passing by adding `"generation_options": {"schedule_mode": "standard"}` or by relying on the standard default, and add one compressed/custom fixture with `daysExactly` matching the selected days.

- [ ] **Step 5: Update generator repair and revision messages**

In `plan_generator._user_message()`, add:

```python
if review_input.review_days:
    meta_parts.append("必须生成的复习日：" + ",".join(str(day) for day in review_input.review_days))
meta_parts.append(f"复习节奏模式：{review_input.schedule_mode}")
if review_input.user_requirements:
    sections.append(
        "【老师本次生成要求】\n"
        + review_input.user_requirements
        + "\n这些要求必须尽量遵守；如果与复习日结构、可打印性、题目完整性、事实准确性冲突，以结构和质量要求优先。"
    )
```

In `_repair_message()`, replace fixed day text with:

```python
required_days_text = ",".join(str(day) for day in review_input.review_days)
"days 必须且只能覆盖所选复习日：" + required_days_text + "；每个 day 必须有可打印的复习任务。"
```

Change `_repair_message()` to accept `review_input`, and update all callers.

In `revision._revision_message()`, replace fixed day text with:

```python
required_days_text = ",".join(str(day) for day in review_input.review_days)
f"必须返回完整 JSON object，且 days 只包含所选复习日：{required_days_text}。"
```

Include `schedule_mode`, `review_days`, and `user_requirements` in the user input JSON.

- [ ] **Step 6: Update prompt files**

In `review_plan_workflow/prompts/nodes/task-generator.md`, replace:

```text
- 固定使用 5 个复习节点：第 1 天、第 2 天、第 7 天、第 14 天、第 30 天。
```

with:

```text
- 必须且只能使用 workflow variables 中 `generation_options.review_days` 指定的复习日。
- `generation_options.schedule_mode` 是本次复习节奏：standard 表示标准间隔，compressed 表示压缩 1 天，daily 表示连续每日，custom 表示自定义日期点。
- 如 `generation_options.user_requirements` 非空，必须作为老师本次生成要求尽量遵守；若与可打印结构、事实准确性或质量门禁冲突，以结构和质量要求优先。
```

In `review_plan_workflow/prompts/nodes/revision.md`, replace fixed-day instructions with the same `generation_options.review_days` wording.

In rubric yaml, replace "5个复习节点必须是第1/2/7/14/30天" with "复习节点必须完整覆盖本次 generation_options.review_days".

Search and remove remaining fixed-day generation hints from `review_plan_workflow/service.py`, `review_plan_workflow/nodes/plan_generator.py`, `review_plan_workflow/nodes/revision.py`, and prompt files. The verification command must include:

```bash
rg -n "固定.*1,2,7,14,30|day=1,2,7,14,30|第 1 天、第 2 天、第 7 天、第 14 天、第 30 天" review_plan_workflow
```

Expected: only historical fixture names or intentionally standard-only test text remain.

- [ ] **Step 7: Update PDF adapter labels**

In `review_plan_templates/single_lesson_pdf.py`, make `adapt_day()` prefer generated day labels before synthesizing `第{day_number}天`:

```python
label = _clean_text(day_data.get("label") or day_data.get("title"), f"第{day_number}天")
...
"day": label,
```

Keep `offset=day_number` so date math still works.

- [ ] **Step 8: Run workflow and quality tests**

Run:

```bash
python3 -m unittest tests.test_review_plan_workflow tests.test_review_plan_generation_options -v
```

Expected: pass.

- [ ] **Step 9: Commit Task 4**

Run:

```bash
git add review_plan_workflow/service.py review_plan_workflow/nodes/plan_generator.py review_plan_workflow/nodes/revision.py review_plan_workflow/prompts/nodes/task-generator.md review_plan_workflow/prompts/nodes/revision.md review_plan_workflow/prompts/rubrics/review-plan-quality.yaml review_plan_workflow/quality_gate.py review_plan_workflow/evals/runner.py review_plan_workflow/evals/fixtures review_plan_templates/single_lesson_pdf.py tests/test_review_plan_workflow.py
git commit -m "feat: enforce selected review days in workflow quality"
```

## Task 5: Frontend Types, Helpers, And Generation Settings Component

**Files:**
- Modify: `frontend/src/features/review-generation/reviewPlanVersions.ts`
- Modify: `frontend/src/reviewGenerationAsync.ts`
- Modify: `frontend/src/reviewGenerationAsync.test.ts`

**Interfaces:**
- Produces: `ReviewGenerationOptions` TypeScript type.
- Produces: normalizers and summary labels for API payloads.

- [ ] **Step 1: Add frontend helper tests**

In `frontend/src/reviewGenerationAsync.test.ts`, add:

```ts
test('normalizes review generation options and summary', () => {
  const options = normalizeReviewGenerationOptions({
    schedule_mode: 'custom',
    review_days: [7, 1, 3, 31],
    user_requirements: '题量少一点',
  });
  assert.equal(options.schedule_mode, 'custom');
  assert.deepEqual(options.review_days, [1, 3, 7]);
  assert.equal(getReviewGenerationSummary(options), '自定义 1,3,7');
});

test('defaults old review versions to standard generation options', () => {
  const detail = normalizeReviewPlanDetail({
    id: 1,
    versions: [{ id: 2, status: 'ready', pdf_available: true }],
  });
  assert.equal(detail?.versions[0]?.generation_summary, '标准 5 次');
  assert.deepEqual(detail?.versions[0]?.generation_options.review_days, [1, 2, 7, 14, 30]);
});
```

- [ ] **Step 2: Run frontend helper tests and confirm failure**

Run:

```bash
npm --prefix frontend exec tsx --test src/reviewGenerationAsync.test.ts
```

Expected: fail because helpers and fields do not exist.

- [ ] **Step 3: Add types and helpers**

In `reviewPlanVersions.ts`, add:

```ts
export type ReviewScheduleMode = 'standard' | 'compressed' | 'daily' | 'custom';

export type ReviewGenerationOptions = {
  schedule_mode: ReviewScheduleMode;
  review_days: number[];
  daily_count: number | null;
  user_requirements: string;
  source: string;
};

export const standardReviewGenerationOptions: ReviewGenerationOptions = {
  schedule_mode: 'standard',
  review_days: [1, 2, 7, 14, 30],
  daily_count: null,
  user_requirements: '',
  source: 'create',
};

export function normalizeReviewGenerationOptions(value: unknown): ReviewGenerationOptions {
  if (!isRecord(value)) {
    return { ...standardReviewGenerationOptions, review_days: [...standardReviewGenerationOptions.review_days] };
  }
  const mode = (
    value.schedule_mode === 'compressed'
    || value.schedule_mode === 'daily'
    || value.schedule_mode === 'custom'
  ) ? value.schedule_mode : 'standard';
  const rawDays = Array.isArray(value.review_days) ? value.review_days : standardReviewGenerationOptions.review_days;
  const reviewDays = [...new Set(rawDays.filter((day): day is number => Number.isInteger(day) && day > 0 && day <= 30))].sort((a, b) => a - b);
  return {
    schedule_mode: mode,
    review_days: reviewDays.length ? reviewDays : [...standardReviewGenerationOptions.review_days],
    daily_count: pickNullableNumber(value.daily_count),
    user_requirements: pickString(value.user_requirements),
    source: pickString(value.source) || 'create',
  };
}

export function getReviewGenerationSummary(options: ReviewGenerationOptions): string {
  if (options.schedule_mode === 'compressed') return '压缩 1 天';
  if (options.schedule_mode === 'daily') return `连续 ${options.review_days.length} 天`;
  if (options.schedule_mode === 'custom') return `自定义 ${options.review_days.join(',')}`;
  return '标准 5 次';
}
```

Extend `ReviewPlanVersionRecord` and `ReviewPlanDetailRecord` with `generation_options` and `generation_summary`. Normalize both fields.

- [ ] **Step 4: Re-export helpers if tests import from async module**

If `frontend/src/reviewGenerationAsync.ts` is the existing test entrypoint, export from there:

```ts
export {
  getReviewGenerationSummary,
  normalizeReviewGenerationOptions,
  standardReviewGenerationOptions,
} from './features/review-generation/reviewPlanVersions';
export type { ReviewGenerationOptions } from './features/review-generation/reviewPlanVersions';
```

- [ ] **Step 5: Run frontend helper tests**

Run:

```bash
npm --prefix frontend exec tsx --test src/reviewGenerationAsync.test.ts
```

Expected: pass.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add frontend/src/features/review-generation/reviewPlanVersions.ts frontend/src/reviewGenerationAsync.ts frontend/src/reviewGenerationAsync.test.ts
git commit -m "feat: normalize review generation options in frontend"
```

## Task 6: Create Modal Settings And Regenerate Dialog

**Files:**
- Modify: `frontend/src/features/review-generation/LessonInput.tsx`
- Modify: `frontend/src/features/review-generation/ReviewGenerationPage.tsx`
- Modify: `frontend/src/features/review-generation/ReviewPlanDetailView.tsx`
- Modify: `frontend/src/review-generation-async.test.tsx`

**Interfaces:**
- Consumes: frontend options helpers from Task 5.
- Produces: create payload includes `generation_options`.
- Produces: regenerate dialog posts edited `generation_options`.

- [ ] **Step 1: Add source-level UI tests**

In `frontend/src/review-generation-async.test.tsx`, add assertions:

```ts
test('review generation create UI includes generation settings and teacher requirements', () => {
  const lessonInputSource = readFileSync(
    new URL('./features/review-generation/LessonInput.tsx', import.meta.url),
    'utf8',
  );
  assert.match(lessonInputSource, /生成设置/);
  assert.match(lessonInputSource, /本次生成要求/);
  assert.match(lessonInputSource, /generation_options/);
  assert.match(lessonInputSource, /schedule_mode/);
});

test('review generation page uses regenerate settings dialog instead of confirm', () => {
  const pageSource = readFileSync(
    new URL('./features/review-generation/ReviewGenerationPage.tsx', import.meta.url),
    'utf8',
  );
  assert.doesNotMatch(pageSource, /确定重新生成《/);
  assert.match(pageSource, /重新生成设置/);
  assert.match(pageSource, /generation_options/);
});
```

- [ ] **Step 2: Run frontend source tests and confirm failure**

Run:

```bash
npm --prefix frontend exec tsx --test src/review-generation-async.test.tsx
```

Expected: fail because UI strings and payloads are missing.

- [ ] **Step 3: Add generation options state in `LessonInput.tsx`**

Import helpers and types:

```ts
import {
  getReviewGenerationSummary,
  type ReviewGenerationOptions,
  standardReviewGenerationOptions,
} from './reviewPlanVersions';
```

Add state:

```ts
const [generationOptions, setGenerationOptions] = useState<ReviewGenerationOptions>(standardReviewGenerationOptions);
const [customDaysText, setCustomDaysText] = useState('1,3,7');
const [dailyCount, setDailyCount] = useState(7);
```

Add builder:

```ts
function buildGenerationOptions(): ReviewGenerationOptions {
  if (generationOptions.schedule_mode === 'compressed') {
    return { ...generationOptions, review_days: [1], daily_count: 1 };
  }
  if (generationOptions.schedule_mode === 'daily') {
    return {
      ...generationOptions,
      review_days: Array.from({ length: Math.max(1, Math.min(30, dailyCount)) }, (_, index) => index + 1),
      daily_count: Math.max(1, Math.min(30, dailyCount)),
    };
  }
  if (generationOptions.schedule_mode === 'custom') {
    const reviewDays = customDaysText
      .split(',')
      .map((part) => Number.parseInt(part.trim(), 10))
      .filter((day) => Number.isInteger(day) && day > 0 && day <= 30)
      .sort((a, b) => a - b);
    return { ...generationOptions, review_days: [...new Set(reviewDays)], daily_count: null };
  }
  return { ...generationOptions, review_days: [1, 2, 7, 14, 30], daily_count: null };
}
```

Validate custom mode before submit:

```ts
const nextGenerationOptions = buildGenerationOptions();
if (nextGenerationOptions.review_days.length === 0) {
  setError('请填写有效的复习日期点');
  return;
}
```

Include `generation_options: nextGenerationOptions` in JSON payload and append `JSON.stringify(nextGenerationOptions)` for multipart.

- [ ] **Step 4: Render generation settings section**

Below "教学信息", add a compact section:

```tsx
<section className={reviewFormSectionClass}>
  <h4 className={reviewFormSectionTitleClass}>生成设置</h4>
  <div className="grid gap-3 sm:grid-cols-2">
    {[
      ['standard', '标准复习', '第 1/2/7/14/30 天'],
      ['compressed', '压缩 1 天', '整节课压成当天复盘'],
      ['daily', '连续每日', '每天一份复习任务'],
      ['custom', '自定义日期点', '例如 1,3,7,14'],
    ].map(([mode, title, description]) => (
      <button
        key={mode}
        type="button"
        onClick={() => setGenerationOptions((current) => ({ ...current, schedule_mode: mode as ReviewGenerationOptions['schedule_mode'] }))}
        className={cn(
          'rounded-xl border px-4 py-3 text-left text-sm transition',
          generationOptions.schedule_mode === mode ? 'border-slate-900 bg-slate-950 text-white' : 'border-slate-200 bg-white text-slate-700',
        )}
      >
        <span className="block font-semibold">{title}</span>
        <span className="mt-1 block text-xs opacity-80">{description}</span>
      </button>
    ))}
  </div>
  {generationOptions.schedule_mode === 'daily' && (
    <input type="number" min={1} max={30} value={dailyCount} onChange={(event) => setDailyCount(Number(event.target.value) || 1)} className={reviewFormFieldClass} />
  )}
  {generationOptions.schedule_mode === 'custom' && (
    <input value={customDaysText} onChange={(event) => setCustomDaysText(event.target.value)} className={reviewFormFieldClass} placeholder="例如：1,3,7,14" />
  )}
  <textarea
    placeholder="本次生成要求（选填）：例如适合明天考试前冲刺、题量少一点、更偏基础、多做选择诊断"
    value={generationOptions.user_requirements}
    onChange={(event) => setGenerationOptions((current) => ({ ...current, user_requirements: event.target.value }))}
    rows={4}
    className={`${reviewFormFieldClass} resize-none`}
  />
</section>
```

In "生成前检查", add rows for schedule summary and requirement presence using `getReviewGenerationSummary(buildGenerationOptions())`.

- [ ] **Step 5: Replace list regenerate confirm with dialog**

In `ReviewGenerationPage.tsx`, add state:

```ts
const [regenerateTarget, setRegenerateTarget] = useState<ReviewLessonRecord | null>(null);
```

Change regenerate button handler to set the target instead of calling API immediately.

Add `RegenerateReviewPlanDialog` component in the same file or a small local component. It accepts:

```ts
type RegenerateReviewPlanDialogProps = {
  lesson: ReviewLessonRecord;
  onClose: () => void;
  onSubmit: (lesson: ReviewLessonRecord, options: ReviewGenerationOptions) => Promise<void>;
};
```

The dialog title is `重新生成设置`, preloads `lesson.generation_options`, and posts:

```ts
await apiFetch<ReviewPlanCreateResult>(`/api/review-plans/${lesson.id}/regenerate`, {
  method: 'POST',
  body: JSON.stringify({ generation_options: options }),
});
```

- [ ] **Step 6: Display generation summaries**

In list cards and `ReviewPlanDetailView.tsx`, render `generation_summary || '标准 5 次'` near version number/time. Keep it small and secondary.

- [ ] **Step 7: Run frontend tests**

Run:

```bash
npm --prefix frontend exec tsx --test src/reviewGenerationAsync.test.ts src/review-generation-async.test.tsx
```

Expected: pass.

- [ ] **Step 8: Commit Task 6**

Run:

```bash
git add frontend/src/features/review-generation/LessonInput.tsx frontend/src/features/review-generation/ReviewGenerationPage.tsx frontend/src/features/review-generation/ReviewPlanDetailView.tsx frontend/src/review-generation-async.test.tsx
git commit -m "feat: add review generation settings UI"
```

## Task 7: Integration Verification, PDF Smoke, Handoff, And Merge

**Files:**
- Modify: `handoff.md`

**Interfaces:**
- Consumes all prior tasks.
- Produces proof that compressed, daily, and custom schedules pass backend validation and render at least one PDF smoke artifact.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
python3 -m unittest \
  tests.test_review_plan_generation_options \
  tests.test_review_plan_async_store \
  tests.test_review_plan_async_api \
  tests.test_review_plan_workflow \
  -v
```

Expected: all tests pass.

- [ ] **Step 2: Run focused frontend tests**

Run:

```bash
npm --prefix frontend exec tsx --test \
  src/reviewGenerationAsync.test.ts \
  src/review-generation-async.test.tsx
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend build**

Run:

```bash
npm --prefix frontend run build
```

Expected: Vite build completes successfully.

- [ ] **Step 4: Run UI smoke for create and regenerate settings**

Run a temporary Playwright smoke against the Vite app after implementation. Use the existing `frontend` Playwright dependency and local test credentials. Verify desktop and mobile widths.

Required checks:

- "生成设置" is visible in the create modal.
- Schedule options do not overflow at 390px mobile width.
- Selecting `压缩 1 天`, `连续每日`, and `自定义日期点` changes the preview summary.
- "本次生成要求" textarea is keyboard-focusable and its text is included in the outgoing `generation_options`.
- Regenerate opens `重新生成设置` instead of `window.confirm`, prefills the previous version options, and posts edited options.

If live auth/data setup is too heavy, implement this as a component-level jsdom test plus a Playwright screenshot of a local fixture route or mounted page shell; do not rely on source-string assertions alone for the final UI quality proof.

- [ ] **Step 5: Run PDF smoke script**

Create a temporary script at `/tmp/proof_review_plan_generation_options_pdf.py` with this structure:

```python
from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf

plan = {
    "lesson_info": {"subject": "数学", "topic": "分式方程压缩复盘", "date": "2026-06-30"},
    "full_review_topics": ["最简公分母", "去分母", "解整式方程", "验根", "增根"],
    "days": [
        {
            "day": 1,
            "label": "当天压缩复盘",
            "goal": "压缩复盘分式方程完整解题链路。",
            "focus": "去分母、解方程、验根、排除增根。",
            "blanks": [
                {"text": "分式方程去分母前先找______。", "answer": "最简公分母"},
                {"text": "去分母后要检查每一项是否都______。", "answer": "乘到"},
                {"text": "解完分式方程必须把解代回______。", "answer": "原分母"},
                {"text": "让原分母为 0 的解叫______。", "answer": "增根"},
                {"text": "验根不通过时应______该解。", "answer": "舍去"},
            ],
            "choices": [
                {
                    "question": "分式方程验根主要为了什么？",
                    "options": ["A. 排除增根", "B. 改变题意", "C. 增加未知数", "D. 删除分母"],
                    "answer": "A",
                },
                {
                    "question": "去分母最容易漏掉哪类项？",
                    "options": ["A. 常数项", "B. 题号", "C. 标点", "D. 单位"],
                    "answer": "A",
                },
                {
                    "question": "如果候选解让原分母等于 0，应怎么处理？",
                    "options": ["A. 舍去", "B. 保留", "C. 平方", "D. 开方"],
                    "answer": "A",
                },
            ],
            "completion_standard": "能完整说出找公分母、去分母、解方程、验根四步。",
        }
    ],
}

path = generate_single_lesson_pdf(plan, "/tmp/review-plan-generation-options-smoke.pdf")
print(path)
```

Run:

```bash
python3 /tmp/proof_review_plan_generation_options_pdf.py
```

Expected: prints a PDF path under `/tmp` and exits 0. If the renderer function name differs, inspect `review_plan_templates/generate_review_pdfs.py` and use the existing single lesson render helper.

- [ ] **Step 6: Run diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Only intended tracked files are modified; untracked runtime artifacts are not staged.

- [ ] **Step 7: Update handoff**

Add one top entry to `handoff.md`:

```markdown
- 2026-06-30 已完成复习计划生成选项与老师本次要求链路实现：版本记录新增 `generation_options_json`，新建和重新生成 API 支持标准 5 次、压缩 1 天、连续每日和自定义日期点，老师本次要求进入 workflow prompt；workflow、revision、quality gate 已按所选 `review_days` 校验；前端新建弹窗新增“生成设置”，重新生成改为设置弹窗并默认沿用上版设置。proof：写入实际通过的命令和结果。当前尚未部署生产。
```

Use the actual proof command results from Steps 1 to 6.

- [ ] **Step 8: Commit final handoff**

Run:

```bash
git add handoff.md
git commit -m "docs: record review generation options implementation"
```

- [ ] **Step 9: Merge back to develop**

Run:

```bash
git switch develop
git pull --ff-only origin develop
git merge --no-ff codex/review-plan-generation-options
git branch -d codex/review-plan-generation-options
git status --short --branch
```

Expected: feature branch merged into `develop`; only unrelated pre-existing untracked runtime artifacts remain.

## Plan Self-Review

Spec coverage:

- Schedule presets and custom days are covered in Tasks 1, 2, 3, 4, 5, and 6.
- Teacher one-off requirements are covered in Tasks 1, 2, 3, 4, and 6.
- Version-level storage and old-data fallback are covered in Tasks 1 and 2.
- Regenerate prefill and editable settings are covered in Tasks 2 and 6.
- Prompt and quality gate parameterization are covered in Tasks 3 and 4.
- Frontend create flow, regenerate dialog, and version summaries are covered in Tasks 5 and 6.
- Verification and PDF smoke are covered in Task 7.

Placeholder scan:

- No placeholder markers or unspecified edge handling remain in this plan.

Type consistency:

- Backend uses `generation_options`, `generation_options_json`, `generation_summary`, `schedule_mode`, `review_days`, `daily_count`, `user_requirements`, and `source` consistently.
- Frontend uses `ReviewGenerationOptions` with the same JSON keys as the backend.
- Workflow uses `ReviewPlanInput.schedule_mode`, `ReviewPlanInput.review_days`, and `ReviewPlanInput.user_requirements` consistently.

## GSTACK REVIEW REPORT

Architecture review:

- [P1] `source` preservation had to be explicit. The plan now preserves saved `source` when reading `generation_options_json`, passes `generation_options_source="regenerate"` for regenerate versions, and asserts it in API tests.
- [P1] Worker recovery was a missing integration point. The plan now requires `_recover_review_plan_generations()` and `_run_review_plan_generation_job()` to forward version-level generation options so service restarts do not silently revert to standard days.
- [P1] The LLM path is the real system boundary. The plan now requires `generate_single_lesson_review_plan()` to accept normalized options, build `ReviewPlanInput` with them, and propagate them through prompt variables, parent-planner fallback, generator repair, revision, quality gate, trace, and PDF smoke.

Code quality review:

- [P1] API error helper shape is fixed in the plan: invalid options return a Flask response tuple as the second value, not a third unpacked value.
- [P1] Test snippets now match real helper signatures and current unittest style.
- [P2] Normalizer tests now reject bool, float, comma-string daily counts, and out-of-range days so input coercion stays explicit rather than clever.
- [P2] Fixed-day wording has an explicit `rg` verification step across workflow code and prompts.

Test review:

```text
CODE PATHS                                           USER FLOWS
[+] generation_options.py                            [+] Create review plan
  ├── [★★★ PLANNED] default/standard                   ├── [★★★ PLANNED] text JSON options reach worker
  ├── [★★★ PLANNED] compressed/daily/custom            ├── [★★★ PLANNED] multipart text file options reach worker
  └── [★★★ PLANNED] invalid bool/float/range           └── [★★★ PLANNED] invalid options show 400
[+] lesson_manager.py                                [+] Regenerate review plan
  ├── [★★★ PLANNED] schema migration/store/read        ├── [★★★ PLANNED] previous options prefill/fallback
  ├── [★★★ PLANNED] source create/regenerate           └── [★★★ PLANNED] edited options create new version
  └── [★★ PLANNED] corrupted JSON fallback
[+] app.py                                           [+] UI settings
  ├── [★★★ PLANNED] create/regenerate/recovery         ├── [★★ PLANNED] create modal settings
  └── [★★★ PLANNED] worker handoff                     └── [★★ PLANNED] regenerate dialog, no confirm
[+] workflow/prompt/quality                           [+] PDF/rendering
  ├── [★★★ PLANNED] selected days in scope/time        ├── [★★ PLANNED] compressed one-day PDF smoke
  ├── [★★★ PLANNED] repair/revision selected days      └── [★★ PLANNED] custom labels survive adapter
  └── [★★★ PLANNED] missing/unexpected day gate

COVERAGE: planned coverage for all critical branches. E2E/UI smoke remains required before merge.
```

Performance review:

- No new database fan-out is planned. Added JSON parsing happens on version serialization and is bounded to one small version object.
- The main performance risk is long custom schedules increasing PDF size and LLM output size. The plan caps schedules at 30 days and adds PDF/build smoke.

NOT in scope:

- Saved teacher prompt templates: deferred because one-off requirements are enough for first release.
- Side-by-side version comparison: deferred to keep regeneration storage and detail view small.
- Requirement-adherence LLM judge: deferred because free-text requirements would create false failures.
- Credit pricing changes: deferred; regenerate continues to use the existing generation credit path.

What already exists:

- Version history and non-overwrite regeneration already exist; the plan reuses `review_plan_versions`.
- Async create/regenerate worker and recovery already exist; the plan extends them with options instead of adding a new job system.
- `review_plan_runs` and Langfuse/local observability already exist; the plan extends summaries instead of adding a second trace store.
- PDF adapter already renders arbitrary `plan.days`; the plan only preserves labels and adds smoke coverage.

Failure modes:

- Invalid options parse fails: covered by API 400 tests; user sees a clear error.
- Service restart during generation: covered by recovery-path requirement; without it the schedule would silently reset.
- LLM emits missing or extra days: covered by quality gate tests and revision instructions.
- Compressed plan under-filled: covered by compressed density guard.
- Custom labels lost in PDF: covered by adapter label change and PDF smoke.
- UI overflows on mobile: covered by required UI smoke at 390px.

Parallelization strategy:

- Sequential implementation is recommended. Backend storage/API, workflow quality, and frontend UI all share the same JSON contract, so parallel worktrees would create avoidable merge and behavior drift.
- If split is necessary, use two lanes only after Task 1 lands: Lane A backend/workflow/PDF, Lane B frontend helpers/UI. Merge Lane A first so frontend contracts are stable.

Outside voice:

- Codex CLI ran in read-only mode and found concrete gaps in test signatures, error helper shape, source preservation, recovery path, hidden fixed-day prompts, PDF labels, observability, normalizer coercion, eval fixtures, and workflow branch hygiene.
- These findings were incorporated into Tasks 0-4 and Task 7. No cross-model tension remains.

Implementation Tasks:

- [ ] **T1 (P1)** — Backend contract — preserve generation option source and expose runnable store/API tests.
  - Surfaced by: architecture/code-quality review.
  - Files: `review_plan_workflow/generation_options.py`, `lesson_manager.py`, `tests/test_review_plan_generation_options.py`, `tests/test_review_plan_async_store.py`, `tests/test_review_plan_async_api.py`
  - Verify: Task 1 and Task 2 unittest commands.
- [ ] **T2 (P1)** — Worker/workflow — pass generation options through create, regenerate, recovery, service, prompt, revision, and quality gate.
  - Surfaced by: architecture/test review.
  - Files: `app.py`, `review_plan_workflow/**`, `tests/test_review_plan_workflow.py`
  - Verify: workflow unittest plus fixed-day wording `rg`.
- [ ] **T3 (P2)** — Frontend/PDF — add settings UI, regenerate dialog, summaries, PDF label preservation, and UI smoke.
  - Surfaced by: product UI and PDF review.
  - Files: `frontend/src/features/review-generation/**`, `frontend/src/reviewGenerationAsync.ts`, `review_plan_templates/single_lesson_pdf.py`
  - Verify: frontend tests, build, UI smoke, PDF smoke.
