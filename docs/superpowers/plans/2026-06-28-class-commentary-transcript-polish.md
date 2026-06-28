# Class Commentary Transcript Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve class-commentary transcription quality by storing raw Tencent ASR text, polishing it with an LLM constrained by the selected class roster, and showing the polished transcript in the existing frontend flow.

**Architecture:** Keep the frontend API contract unchanged. Add private transcript polish storage fields, sanitize the roster before prompt/storage, add a transcript-polish AI helper, and update the existing transcription worker to run ASR first and LLM polish second with a distinct usage identity.

**Tech Stack:** Flask, SQLite, Python unittest/pytest, existing AI client wrapper in `ai_processor.py`, existing charge wrapper in `app.py`, existing React frontend unchanged.

## Global Constraints

- Do not change the current frontend flow in this phase.
- Do not ask teachers to type student names.
- Use the selected `class_id` to fetch the existing class roster from the backend.
- Do not create or manage Tencent Cloud hotword tables in this phase.
- The teacher-facing transcript box should show the LLM-polished transcript by default.
- The raw Tencent ASR transcript should be stored server-side for audit/debugging.
- Store a roster snapshot with each transcription attempt so later roster edits do not make the polish decision impossible to audit.
- The roster payload sent to the LLM and stored in `roster_snapshot` must contain only sanitized roster items: `id`, `name`, and optionally `class_student_id` if implementation needs it.
- Do not include `parent_contact`, `source`, `status`, `archived_at`, `created_at`, or any other raw student metadata in the polish prompt or `roster_snapshot`.
- If transcript polishing fails after ASR succeeds, the task should still become `transcribed` with the raw ASR text visible, so teachers can manually edit and continue.
- Feedback generation continues to use `confirmed_transcript_text`, not the raw ASR text.
- API task responses must not include `raw_transcript_text`, `roster_snapshot`, `transcript_polish_error`, or `transcript_polished_at`.
- Transcript polish must use a distinct usage identity from ASR, preferably `class_commentary_transcript_polish`.
- No frontend tests are required unless the API response shape changes.

---

## File Structure

- Modify `class_commentary.py`
  - Add sanitized roster helper.
  - Add transcript polish payload builder and math term list.
  - Keep existing feedback-generation payload behavior unchanged.
- Modify `ai_processor.py`
  - Add `polish_class_commentary_transcript(...)`.
  - Use the existing chat model and usage helpers.
- Modify `lesson_manager.py`
  - Add private columns to `class_commentary_tasks`.
  - Add store/update helpers for ASR raw text, roster snapshot, polish success, and polish fallback.
  - Preserve private polish fields across manual transcript save and generation updates.
- Modify `app.py`
  - Keep `_serialize_class_commentary_task_for_response()` as the public allowlist and add tests around it.
  - Update `_run_class_commentary_transcription()` to fetch class/roster, run ASR, then run polish with a distinct feature key.
- Modify `credit_manager.py`
  - Add pricing for `class_commentary_transcript_polish`.
- Modify `tests/test_class_commentary_ai.py`
  - Add prompt/payload tests for sanitized roster and polish helper contract.
- Modify `tests/test_class_commentary_api.py`
  - Add worker, fallback, lifecycle, and response privacy tests.
- Modify `tests/test_credit_system.py`
  - Add pricing assertion for `class_commentary_transcript_polish`.
- No frontend files should change.

---

### Task 1: Storage Fields And Public API Privacy

**Files:**
- Modify: `lesson_manager.py`
- Modify: `app.py`
- Modify: `tests/test_class_commentary_api.py`

**Interfaces:**
- Produces: private task fields `raw_transcript_text`, `roster_snapshot`, `transcript_polish_error`, `transcript_polished_at`.
- Produces: `lesson_manager.mark_class_commentary_raw_transcription_succeeded(task_id: int, raw_transcript_text: str, roster_snapshot: str) -> dict`.
- Produces: `lesson_manager.mark_class_commentary_transcript_polish_succeeded(task_id: int, polished_transcript_text: str) -> dict`.
- Produces: `lesson_manager.mark_class_commentary_transcript_polish_failed(task_id: int, raw_transcript_text: str, error_message: str) -> dict`.
- Preserves: `_serialize_class_commentary_task_for_response(task)` returns only public fields.

- [ ] **Step 1: Write failing API privacy and lifecycle tests**

Add this constant and tests to `tests/test_class_commentary_api.py` inside `ClassCommentaryApiTestCase`:

```python
    PRIVATE_TRANSCRIPT_POLISH_FIELDS = {
        "raw_transcript_text",
        "roster_snapshot",
        "transcript_polish_error",
        "transcript_polished_at",
    }

    def assertPrivateTranscriptPolishFieldsHidden(self, payload: dict):
        for field_name in self.PRIVATE_TRANSCRIPT_POLISH_FIELDS:
            self.assertNotIn(field_name, payload)

    def test_task_response_hides_private_transcript_polish_fields(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )
        lesson_manager.mark_class_commentary_raw_transcription_succeeded(
            task["id"],
            "小汪今天计算有进步",
            '[{"id": 1, "name": "小王"}]',
        )
        lesson_manager.mark_class_commentary_transcript_polish_succeeded(
            task["id"],
            "小王今天计算有进步",
        )

        response = self.client.get(
            f"/api/class-commentary/tasks/{task['id']}",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["transcript_text"], "小王今天计算有进步")
        self.assertPrivateTranscriptPolishFieldsHidden(payload)

    def test_manual_transcript_save_preserves_private_polish_fields(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )
        lesson_manager.mark_class_commentary_raw_transcription_succeeded(
            task["id"],
            "小汪今天计算有进步",
            '[{"id": 1, "name": "小王"}]',
        )
        lesson_manager.mark_class_commentary_transcript_polish_failed(
            task["id"],
            "小汪今天计算有进步",
            "model timeout",
        )

        updated = lesson_manager.save_class_commentary_transcript(task["id"], "小王今天计算有进步")

        self.assertEqual(updated["confirmed_transcript_text"], "小王今天计算有进步")
        self.assertEqual(updated["raw_transcript_text"], "小汪今天计算有进步")
        self.assertEqual(updated["roster_snapshot"], '[{"id": 1, "name": "小王"}]')
        self.assertEqual(updated["transcript_polish_error"], "model timeout")
        self.assertEqual(updated["transcript_polished_at"], "")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_class_commentary_api.py -q
```

Expected: FAIL with missing `mark_class_commentary_raw_transcription_succeeded` or missing private fields.

- [ ] **Step 3: Add columns to the table schema and migration**

In `lesson_manager.py`, extend the `CREATE TABLE IF NOT EXISTS class_commentary_tasks` block with:

```sql
                raw_transcript_text TEXT NOT NULL DEFAULT '',
                roster_snapshot TEXT NOT NULL DEFAULT '',
                transcript_polish_error TEXT NOT NULL DEFAULT '',
                transcript_polished_at TEXT NOT NULL DEFAULT '',
```

Place these after `transcript_text TEXT NOT NULL DEFAULT ''`.

After the `conn.executescript(...)` block that creates `class_commentary_tasks`, add:

```python
        _ensure_column(conn, "class_commentary_tasks", "raw_transcript_text", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "class_commentary_tasks", "roster_snapshot", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "class_commentary_tasks", "transcript_polish_error", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "class_commentary_tasks", "transcript_polished_at", "TEXT NOT NULL DEFAULT ''")
```

- [ ] **Step 4: Include private fields in internal task serialization**

In `_serialize_class_commentary_task_row()`, add these to `string_fields`:

```python
        "raw_transcript_text",
        "roster_snapshot",
        "transcript_polish_error",
        "transcript_polished_at",
```

Do not add these fields to `_serialize_class_commentary_task_for_response()` in `app.py`.

- [ ] **Step 5: Add storage helper functions**

In `lesson_manager.py`, replace `mark_class_commentary_transcription_succeeded()` with this implementation and add the new helpers below it:

```python
def mark_class_commentary_raw_transcription_succeeded(task_id: int, raw_transcript_text: str, roster_snapshot: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET raw_transcript_text=?,
                roster_snapshot=?,
                transcript_text=?,
                confirmed_transcript_text=?,
                transcript_polish_error='',
                transcript_polished_at='',
                transcription_error='',
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (raw_transcript_text or "", roster_snapshot or "", raw_transcript_text or "", raw_transcript_text or "", task_id),
        )
    return get_class_commentary_task(task_id)


def mark_class_commentary_transcript_polish_succeeded(task_id: int, polished_transcript_text: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET status='transcribed',
                failure_stage='',
                transcript_text=?,
                confirmed_transcript_text=?,
                transcribed_at=datetime('now','localtime'),
                transcript_polish_error='',
                transcript_polished_at=datetime('now','localtime'),
                transcription_error='',
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (polished_transcript_text or "", polished_transcript_text or "", task_id),
        )
    return get_class_commentary_task(task_id)


def mark_class_commentary_transcript_polish_failed(task_id: int, raw_transcript_text: str, error_message: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE class_commentary_tasks
            SET status='transcribed',
                failure_stage='',
                transcript_text=?,
                confirmed_transcript_text=?,
                transcribed_at=datetime('now','localtime'),
                transcript_polish_error=?,
                transcript_polished_at='',
                transcription_error='',
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (raw_transcript_text or "", raw_transcript_text or "", error_message or "", task_id),
        )
    return get_class_commentary_task(task_id)


def mark_class_commentary_transcription_succeeded(task_id: int, transcript_text: str):
    mark_class_commentary_raw_transcription_succeeded(task_id, transcript_text or "", "")
    return mark_class_commentary_transcript_polish_succeeded(task_id, transcript_text or "")
```

This keeps existing tests and callers working while new code uses the finer helpers.

- [ ] **Step 6: Ensure generation updates preserve private fields**

Review `save_class_commentary_generation_started()` and `save_class_commentary_generation_succeeded()`. Do not add any assignments to `raw_transcript_text`, `roster_snapshot`, `transcript_polish_error`, or `transcript_polished_at`.

Review `save_class_commentary_transcript()`. Do not add any assignments to `raw_transcript_text`, `roster_snapshot`, `transcript_polish_error`, or `transcript_polished_at`.

- [ ] **Step 7: Run tests**

Run:

```bash
python3 -m pytest tests/test_class_commentary_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add lesson_manager.py app.py tests/test_class_commentary_api.py
git commit -m "feat: store class commentary transcript polish metadata"
```

---

### Task 2: Sanitized Roster And Transcript Polish Prompt Payload

**Files:**
- Modify: `class_commentary.py`
- Modify: `tests/test_class_commentary_ai.py`

**Interfaces:**
- Produces: `sanitize_class_commentary_roster(students: list[dict]) -> list[dict]`.
- Produces: `CLASS_COMMENTARY_TRANSCRIPT_POLISH_MATH_TERMS: tuple[str, ...]`.
- Produces: `build_class_commentary_transcript_polish_payload(class_record: dict, students: list[dict], raw_transcript_text: str, math_terms: list[str] | tuple[str, ...] | None = None) -> dict`.
- Consumed by: Task 3 and Task 4.

- [ ] **Step 1: Write failing sanitized roster tests**

Add these tests to `tests/test_class_commentary_ai.py`:

```python
    def test_sanitize_class_commentary_roster_keeps_only_id_and_name(self):
        roster = class_commentary.sanitize_class_commentary_roster([
            {
                "id": 1,
                "name": " 小王 ",
                "parent_contact": "secret",
                "source": "wechat",
                "status": "active",
                "archived_at": "2026-06-01",
                "created_at": "2026-06-28",
                "extra_metadata": "private",
            },
            {"id": 2, "name": "   "},
            {"id": "3", "name": "小李", "created_at": "2026-06-28", "extra_metadata": "private"},
        ])

        self.assertEqual(roster, [{"id": 1, "name": "小王"}, {"id": 3, "name": "小李"}])
        serialized = str(roster)
        for forbidden in ["parent_contact", "source", "status", "archived_at", "created_at", "extra_metadata"]:
            self.assertNotIn(forbidden, serialized)

    def test_transcript_polish_payload_uses_sanitized_roster_and_math_terms(self):
        payload = class_commentary.build_class_commentary_transcript_polish_payload(
            class_record={"id": 7, "name": "数学·七年级·4班"},
            students=[{
                "id": 1,
                "name": "小王",
                "parent_contact": "secret",
                "source": "wechat",
                "status": "active",
                "archived_at": "2026-06-01",
                "created_at": "2026-06-28",
                "extra_metadata": "private",
            }],
            raw_transcript_text="小汪今天绝对纸学得不错",
            math_terms=["绝对值", "整式"],
        )

        self.assertEqual(payload["class"], {"id": 7, "name": "数学·七年级·4班"})
        self.assertEqual(payload["students"], [{"id": 1, "name": "小王"}])
        self.assertEqual(payload["math_terms"], ["绝对值", "整式"])
        self.assertIn("小汪今天", payload["raw_transcript"])
        serialized_payload = class_commentary.payload_to_json(payload)
        for forbidden in ["parent_contact", "source", "status", "archived_at", "created_at", "extra_metadata"]:
            self.assertNotIn(forbidden, serialized_payload)
        self.assertIn("Only correct student names to names in students.", payload["rules"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_class_commentary_ai.py -q
```

Expected: FAIL with missing helper functions.

- [ ] **Step 3: Add sanitized roster helper and math terms**

In `class_commentary.py`, add:

```python
CLASS_COMMENTARY_TRANSCRIPT_POLISH_MATH_TERMS = (
    "绝对值",
    "整式",
    "单项式",
    "多项式",
    "方程",
    "不等式",
    "计算",
    "推理",
    "分类讨论",
    "流程图",
    "取值无关",
    "解题过程",
)


def sanitize_class_commentary_roster(students: list[dict]) -> list[dict]:
    roster = []
    for item in students:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            student_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            student_id = 0
        if student_id <= 0:
            continue
        roster.append({"id": student_id, "name": name})
    return roster
```

- [ ] **Step 4: Add transcript polish payload builder**

In `class_commentary.py`, add:

```python
def build_class_commentary_transcript_polish_payload(
    *,
    class_record: dict,
    students: list[dict],
    raw_transcript_text: str,
    math_terms: list[str] | tuple[str, ...] | None = None,
) -> dict:
    terms = [str(item).strip() for item in (math_terms or CLASS_COMMENTARY_TRANSCRIPT_POLISH_MATH_TERMS) if str(item).strip()]
    return {
        "class": {"id": int(class_record["id"]), "name": str(class_record.get("name") or "")},
        "students": sanitize_class_commentary_roster(students),
        "math_terms": terms,
        "raw_transcript": str(raw_transcript_text or "").strip(),
        "rules": [
            "Only correct ASR recognition errors, punctuation, and light sentence boundaries.",
            "Only correct student names to names in students.",
            "If a likely name cannot be confidently mapped to one listed student, keep the raw wording.",
            "Do not add students who are not clearly mentioned.",
            "Do not rewrite this into parent feedback.",
            "Do not change meaning, tone, praise, criticism, reminders, or factual claims.",
            "Use math_terms only to correct obvious ASR mistakes; do not add topics.",
            "Return plain text only.",
        ],
    }
```

- [ ] **Step 5: Refactor feedback payload to reuse sanitized roster**

In `build_class_commentary_generation_payload()`, replace the local `roster = [...]` comprehension with:

```python
    roster = sanitize_class_commentary_roster(students)
```

- [ ] **Step 6: Run tests**

Run:

```bash
python3 -m pytest tests/test_class_commentary_ai.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add class_commentary.py tests/test_class_commentary_ai.py
git commit -m "feat: add class commentary roster polish payload"
```

---

### Task 3: LLM Transcript Polish Helper

**Files:**
- Modify: `ai_processor.py`
- Modify: `tests/test_class_commentary_ai.py`

**Interfaces:**
- Consumes: `class_commentary.build_class_commentary_transcript_polish_payload(...)`.
- Produces: `ai_processor.polish_class_commentary_transcript(class_record: dict, students: list[dict], raw_transcript_text: str, math_terms: list[str] | tuple[str, ...] | None = None, include_usage: bool = False)`.
- Return: `str` by default, `(str, usage_dict)` with `include_usage=True`.

- [ ] **Step 1: Write failing helper test**

Add this test to `tests/test_class_commentary_ai.py`:

```python
    def test_polish_class_commentary_transcript_uses_roster_prompt_contract(self):
        class FakeMessage:
            content = "小王今天绝对值学得不错。"

        class FakeChoice:
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]
            usage = None

        class FakeCompletions:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return FakeResponse()

        class FakeChat:
            def __init__(self):
                self.completions = FakeCompletions()

        class FakeClient:
            def __init__(self):
                self.chat = FakeChat()

        fake_client = FakeClient()
        with patch.object(ai_processor, "_get_client", return_value=fake_client):
            text, usage = ai_processor.polish_class_commentary_transcript(
                class_record={"id": 7, "name": "数学·七年级·4班"},
                students=[{
                    "id": 1,
                    "name": "小王",
                    "parent_contact": "secret",
                    "source": "wechat",
                    "status": "active",
                    "archived_at": "2026-06-01",
                    "created_at": "2026-06-28",
                    "extra_metadata": "private",
                }],
                raw_transcript_text="小汪今天绝对纸学得不错",
                math_terms=["绝对值"],
                include_usage=True,
            )

        self.assertEqual(text, "小王今天绝对值学得不错。")
        self.assertEqual(usage["provider"], ai_processor._provider_name())
        messages = fake_client.chat.completions.kwargs["messages"]
        self.assertIn("correcting ASR text", messages[0]["content"])
        self.assertIn("Do not rewrite", messages[0]["content"])
        user_payload = messages[1]["content"]
        self.assertIn("小王", user_payload)
        self.assertIn("绝对值", user_payload)
        for forbidden in ["parent_contact", "source", "status", "archived_at", "created_at", "extra_metadata"]:
            self.assertNotIn(forbidden, user_payload)
        self.assertEqual(fake_client.chat.completions.kwargs["temperature"], 0.1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_class_commentary_ai.py -q
```

Expected: FAIL with missing `polish_class_commentary_transcript`.

- [ ] **Step 3: Import payload builder in `ai_processor.py`**

At the existing `class_commentary` import site in `ai_processor.py`, add:

```python
from class_commentary import build_class_commentary_transcript_polish_payload
```

If `ai_processor.py` already imports specific functions from `class_commentary`, merge this into that import rather than adding a duplicate.

- [ ] **Step 4: Add polish helper**

Place this near `generate_class_commentary_feedback()` in `ai_processor.py`:

```python
def polish_class_commentary_transcript(
    *,
    class_record: dict,
    students: list[dict],
    raw_transcript_text: str,
    math_terms: list[str] | tuple[str, ...] | None = None,
    include_usage: bool = False,
):
    client = _get_client()
    payload = build_class_commentary_transcript_polish_payload(
        class_record=class_record,
        students=students,
        raw_transcript_text=raw_transcript_text,
        math_terms=math_terms,
    )
    system_prompt = (
        "You are correcting ASR text for a teacher's spoken post-class student commentary. "
        "Only correct recognition errors, punctuation, light sentence boundaries, and roster-name mistakes. "
        "Do not rewrite this into parent feedback. "
        "Do not change meaning, tone, praise, criticism, reminders, next actions, or factual claims. "
        "Do not invent absent students or facts. "
        "Return plain text only."
    )
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload_to_json(payload)},
        ],
        temperature=0.1,
    )
    text = (response.choices[0].message.content or "").strip()
    if include_usage:
        return text, _usage_dict(response)
    return text
```

- [ ] **Step 5: Run tests**

Run:

```bash
python3 -m pytest tests/test_class_commentary_ai.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ai_processor.py tests/test_class_commentary_ai.py
git commit -m "feat: add class commentary transcript polish helper"
```

---

### Task 4: Worker Orchestration And Fallback

**Files:**
- Modify: `app.py`
- Modify: `tests/test_class_commentary_api.py`

**Interfaces:**
- Consumes: Task 1 storage helpers.
- Consumes: Task 2 `sanitize_class_commentary_roster(...)`.
- Consumes: Task 3 `polish_class_commentary_transcript(...)`.
- Produces: transcription worker flow that runs ASR and polish as separate charged AI feature calls.

- [ ] **Step 1: Update imports in `app.py`**

Add these imports:

```python
from class_commentary import list_colleague_skills, load_colleague_skill, sanitize_class_commentary_roster
from ai_processor import generate_class_commentary_feedback, parse_consultation_batch_text, polish_class_commentary_transcript, transcribe_audio
```

Keep one import per module, not duplicate import lines.

- [ ] **Step 2: Update `lesson_manager` imports in `app.py`**

Add:

```python
    mark_class_commentary_raw_transcription_succeeded,
    mark_class_commentary_transcript_polish_failed,
    mark_class_commentary_transcript_polish_succeeded,
```

to the existing `from lesson_manager import (...)` block.

- [ ] **Step 3: Write failing worker success test**

Replace `test_worker_success_moves_task_to_transcribed()` in `tests/test_class_commentary_api.py` with:

```python
    def test_worker_success_stores_raw_and_polished_transcript(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )

        calls = []

        def fake_charge(**kwargs):
            calls.append(kwargs)
            if kwargs["feature_key"] == "class_commentary_transcribe":
                return "小汪今天绝对纸学得不错"
            if kwargs["feature_key"] == "class_commentary_transcript_polish":
                producer_result = kwargs["producer"]()
                self.assertEqual(producer_result[0], "小王今天绝对值学得不错")
                return producer_result[0]
            raise AssertionError(f"unexpected feature key: {kwargs['feature_key']}")

        with patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge), \
             patch.object(self.app_module, "polish_class_commentary_transcript", return_value=("小王今天绝对值学得不错", {"provider": "test", "model": "chat"})) as polish:
            self.app_module._run_class_commentary_transcription(
                task["id"],
                str(self.base / "audio.m4a"),
                {"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
                "saved-audio-request-key",
            )

        saved = lesson_manager.get_class_commentary_task(task["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "transcribed")
        self.assertEqual(saved["raw_transcript_text"], "小汪今天绝对纸学得不错")
        self.assertEqual(saved["transcript_text"], "小王今天绝对值学得不错")
        self.assertEqual(saved["confirmed_transcript_text"], "小王今天绝对值学得不错")
        self.assertEqual(saved["transcript_polish_error"], "")
        self.assertTrue(saved["transcript_polished_at"])
        self.assertIn('"name": "小王"', saved["roster_snapshot"])
        self.assertNotIn("parent_contact", saved["roster_snapshot"])
        self.assertEqual([call["feature_key"] for call in calls], ["class_commentary_transcribe", "class_commentary_transcript_polish"])
        self.assertEqual(calls[0]["request_key"], "saved-audio-request-key")
        self.assertEqual(calls[1]["request_key"], "saved-audio-request-key")
        self.assertEqual(calls[1]["source_record_type"], "class_commentary_transcript_polish")
        polish.assert_called_once()
```

- [ ] **Step 4: Add failing polish fallback test**

Add:

```python
    def test_worker_polish_failure_falls_back_to_raw_transcript(self):
        class_id = self._create_class_with_student()
        task = lesson_manager.create_class_commentary_task(
            organization_id=self.owner["organization_id"],
            class_id=class_id,
            teacher_user_id=self.owner["id"],
            audio_path=str(self.base / "audio.m4a"),
            audio_filename="audio.m4a",
        )

        def fake_charge(**kwargs):
            if kwargs["feature_key"] == "class_commentary_transcribe":
                return "小汪今天绝对纸学得不错"
            if kwargs["feature_key"] == "class_commentary_transcript_polish":
                raise RuntimeError("polish timeout")
            raise AssertionError(f"unexpected feature key: {kwargs['feature_key']}")

        with patch.object(self.app_module, "_run_ai_feature_with_charge", side_effect=fake_charge):
            self.app_module._run_class_commentary_transcription(
                task["id"],
                str(self.base / "audio.m4a"),
                {"id": self.owner["id"], "organization_id": self.owner["organization_id"]},
                "saved-audio-request-key",
            )

        saved = lesson_manager.get_class_commentary_task(task["id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["status"], "transcribed")
        self.assertEqual(saved["raw_transcript_text"], "小汪今天绝对纸学得不错")
        self.assertEqual(saved["transcript_text"], "小汪今天绝对纸学得不错")
        self.assertEqual(saved["confirmed_transcript_text"], "小汪今天绝对纸学得不错")
        self.assertEqual(saved["transcript_polish_error"], "polish timeout")
        self.assertEqual(saved["transcript_polished_at"], "")
        self.assertEqual(saved["failure_stage"], "")
        self.assertEqual(saved["transcription_error"], "")
```

- [ ] **Step 5: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_class_commentary_api.py -q
```

Expected: FAIL because the worker does not yet run polish.

- [ ] **Step 6: Update `_run_class_commentary_transcription()`**

Replace the function body in `app.py` with this flow:

```python
def _run_class_commentary_transcription(task_id: int, audio_path: str, user: dict, request_key: str) -> None:
    try:
        transcription = _run_ai_feature_with_charge(
            user=user,
            feature_key="class_commentary_transcribe",
            source_record_type="class_commentary_task",
            source_record_id=task_id,
            provider=_audio_transcription_provider_name(),
            model=_audio_transcription_model_name(),
            producer=lambda: _call_ai_helper_with_usage(transcribe_audio, audio_path),
            request_key=request_key,
            claim_request_identity=False,
        )
        raw_text = str(transcription or "").strip()
        if not raw_text:
            raise ValueError("transcription returned empty text")

        task = get_class_commentary_task(task_id)
        if not task:
            raise LookupError("class commentary task not found")
        cls = get_class(int(task["class_id"]))
        if not cls:
            raise LookupError("class not found")
        class_students = list_students_for_class(int(task["class_id"]))
        sanitized_roster = sanitize_class_commentary_roster(class_students)
        roster_snapshot = payload_to_json({"students": sanitized_roster})
        mark_class_commentary_raw_transcription_succeeded(task_id, raw_text, roster_snapshot)

        try:
            chat_provider = _review_plan_ai_provider_name()
            chat_model = _review_plan_chat_model_name()
            polished_text = _run_ai_feature_with_charge(
                user=user,
                feature_key="class_commentary_transcript_polish",
                source_record_type="class_commentary_transcript_polish",
                source_record_id=task_id,
                provider=chat_provider,
                model=chat_model,
                producer=lambda: _call_ai_helper_with_usage(
                    polish_class_commentary_transcript,
                    class_record=cls,
                    students=sanitized_roster,
                    raw_transcript_text=raw_text,
                ),
                request_key=request_key,
                claim_request_identity=False,
            )
            polished_text = str(polished_text or "").strip()
            if not polished_text:
                raise ValueError("transcript polish returned empty text")
            mark_class_commentary_transcript_polish_succeeded(task_id, polished_text)
        except Exception as polish_exc:
            mark_class_commentary_transcript_polish_failed(task_id, raw_text, str(polish_exc))
    except Exception as exc:
        mark_class_commentary_task_failed(task_id, "transcription", str(exc))
```

Add these helper functions near `_review_plan_ai_provider_name()` if they do not already exist:

```python
def _audio_transcription_provider_name() -> str:
    return str(get_config().get("audio_transcription_provider") or "local")


def _audio_transcription_model_name() -> str:
    if _audio_transcription_provider_name() == "tencent":
        return f"flash-{get_config().get('tencent_asr_engine_type') or '16k_zh'}"
    return "faster-whisper"
```

Also import `payload_to_json` from `class_commentary` in `app.py`.

- [ ] **Step 7: Run worker tests**

Run:

```bash
python3 -m pytest tests/test_class_commentary_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app.py tests/test_class_commentary_api.py
git commit -m "feat: polish class commentary transcripts after asr"
```

---

### Task 5: Credit Pricing And Usage Regression

**Files:**
- Modify: `credit_manager.py`
- Modify: `tests/test_credit_system.py`
- Modify: `tests/test_class_commentary_api.py`

**Interfaces:**
- Produces: pricing for `class_commentary_transcript_polish`.
- Verifies: ASR and polish use distinct ledger identities.

- [ ] **Step 1: Write failing pricing test**

In `tests/test_credit_system.py`, update `test_class_commentary_feature_keys_are_configured` to:

```python
    def test_class_commentary_feature_keys_are_configured(self):
        self.assertEqual(credit_manager.max_configured_charge_for_feature("class_commentary_transcribe"), 4)
        self.assertEqual(credit_manager.max_configured_charge_for_feature("class_commentary_transcript_polish"), 4)
        self.assertEqual(credit_manager.max_configured_charge_for_feature("class_commentary_generate"), 10)
```

- [ ] **Step 2: Run pricing test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_credit_system.py::CreditSystemTestCase::test_class_commentary_feature_keys_are_configured -q
```

Expected: FAIL with unknown feature key.

- [ ] **Step 3: Add pricing**

In `credit_manager.py`, add this next to `class_commentary_transcribe`:

```python
    "class_commentary_transcript_polish": {"base_credits": 4, "extra_token_threshold": 0, "extra_credits": 0},
```

This deliberately matches the first-version test expectation and avoids surprise credit changes.

- [ ] **Step 4: Add request identity regression test**

In `tests/test_class_commentary_api.py`, extend the success worker test from Task 4 by keeping this assertion:

```python
        self.assertEqual(calls[1]["source_record_type"], "class_commentary_transcript_polish")
```

Add one more assertion:

```python
        self.assertNotEqual(
            (calls[0]["feature_key"], calls[0]["source_record_type"], calls[0]["source_record_id"]),
            (calls[1]["feature_key"], calls[1]["source_record_type"], calls[1]["source_record_id"]),
        )
```

- [ ] **Step 5: Run credit and class-commentary tests**

Run:

```bash
python3 -m pytest tests/test_credit_system.py::CreditSystemTestCase::test_class_commentary_feature_keys_are_configured tests/test_class_commentary_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add credit_manager.py tests/test_credit_system.py tests/test_class_commentary_api.py
git commit -m "feat: price class commentary transcript polish"
```

---

### Task 6: Full Regression And Deployment Readiness

**Files:**
- Modify: `handoff.md`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified implementation ready for review/deploy.

- [ ] **Step 1: Run focused backend regression**

Create and run a temporary proof script:

```bash
cat > /tmp/proof_class_commentary_transcript_polish_20260628.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /Users/ark.mini/Desktop/Desktop\ -\ Ark.1/Xingrun-Website
python3 -m py_compile app.py ai_processor.py class_commentary.py lesson_manager.py credit_manager.py
python3 -m pytest \
  tests/test_class_commentary_api.py \
  tests/test_class_commentary_ai.py \
  tests/test_credit_system.py::CreditSystemTestCase::test_class_commentary_feature_keys_are_configured \
  tests/test_runtime_config_hygiene.py \
  -q
git diff --check -- app.py ai_processor.py class_commentary.py lesson_manager.py credit_manager.py tests/test_class_commentary_api.py tests/test_class_commentary_ai.py tests/test_credit_system.py
SH
chmod +x /tmp/proof_class_commentary_transcript_polish_20260628.sh
/tmp/proof_class_commentary_transcript_polish_20260628.sh
```

Expected: py_compile passes, tests pass, diff check passes.

- [ ] **Step 2: Confirm no frontend files changed**

Run:

```bash
git diff --name-only HEAD~5..HEAD | rg '^frontend/' && exit 1 || echo 'frontend_changes=none'
```

Expected:

```text
frontend_changes=none
```

- [ ] **Step 3: Update handoff**

In `handoff.md`, update the class-commentary transcript polish entry to state:

```text
2026-06-28 已完成 class-commentary 转写校对增强实现: 后端在腾讯云 ASR 后使用 sanitized 班级 roster + 数学术语约束做 LLM 校对, 页面仍显示原有转写框且默认展示校对稿; raw ASR, roster_snapshot 和 polish metadata 仅后端保存且 API 不返回. proof 已通过 /tmp/proof_class_commentary_transcript_polish_20260628.sh.
```

- [ ] **Step 4: Run final proof after handoff**

Run:

```bash
/tmp/proof_class_commentary_transcript_polish_20260628.sh
git diff --check -- handoff.md
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py ai_processor.py class_commentary.py lesson_manager.py credit_manager.py tests/test_class_commentary_api.py tests/test_class_commentary_ai.py tests/test_credit_system.py handoff.md
git commit -m "feat: polish class commentary transcripts"
```

---

## Plan Self-Review

### Spec Coverage

- Frontend unchanged: covered by Global Constraints and Task 6 no-frontend check.
- Existing class roster only: covered by Task 2 sanitized roster and Task 4 worker fetch.
- No Tencent hotword tables: covered by Global Constraints; no task creates hotword tables.
- Teacher-visible polished transcript: covered by Task 1 storage helpers and Task 4 worker success.
- Raw ASR server-side only: covered by Task 1 private fields and API privacy tests.
- Sanitized roster snapshot: covered by Task 2 helper and Task 4 worker storage assertions.
- Polish failure fallback: covered by Task 4 fallback test.
- Usage identity separation: covered by Task 5 pricing and worker call assertions.
- Field lifecycle: covered by Task 1 manual-save preservation test and Task 4 success/failure metadata assertions.
- API response privacy: covered by Task 1 API response test.

### Placeholder Scan

No placeholder markers or vague "write tests" steps are intentionally present. Every task contains concrete files, code snippets, commands, and expected results.

### Type Consistency

- `sanitize_class_commentary_roster(students: list[dict]) -> list[dict]` is defined in Task 2 and consumed by Task 4.
- `build_class_commentary_transcript_polish_payload(...) -> dict` is defined in Task 2 and consumed by Task 3.
- `polish_class_commentary_transcript(...)` is defined in Task 3 and consumed by Task 4.
- Storage helper names in Task 1 match imports and calls in Task 4.
