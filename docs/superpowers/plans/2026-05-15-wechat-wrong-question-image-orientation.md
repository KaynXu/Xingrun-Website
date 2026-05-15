# WeChat Wrong Question Image Orientation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store the AI-detected clockwise rotation for parent-uploaded wrong-question images and use it when rendering geometry images in student wrong-question library PDFs.

**Architecture:** The vision prompt and normalization layer own the `image_rotation_degrees` contract. The upload worker persists the normalized integer on `wrong_question_submissions`. The PDF engine rotates fetched geometry images immediately after download, so both browser rendering and ReportLab fallback receive corrected bytes.

**Tech Stack:** Python, Flask worker/data layer, SQLite migrations in `lesson_manager.py`, ReportLab/Pillow image handling, `unittest`.

---

### Task 1: Recognition Contract

**Files:**
- Modify: `ai_processor.py`
- Test: `tests/test_ai_processor_prompt.py`
- Test: `tests/test_wrong_question_library_pdf.py`

- [ ] **Step 1: Write failing prompt/normalization tests**

Add assertions that `WRONG_QUESTION_RECOGNITION_PROMPT` mentions `image_rotation_degrees`, `0/90/180/270`, and clockwise rotation. Add normalization tests:

```python
normalized = ai_processor._normalize_wrong_question_recognition_result({
    "is_geometry": True,
    "question_text": "",
    "confidence": "high",
    "notes": "",
    "image_rotation_degrees": 90,
})
self.assertEqual(normalized["image_rotation_degrees"], 90)

normalized = ai_processor._normalize_wrong_question_recognition_result({
    "is_geometry": False,
    "question_text": "计算 $1+1$。",
    "confidence": "high",
    "notes": "",
    "image_rotation_degrees": 45,
})
self.assertEqual(normalized["image_rotation_degrees"], 0)
```

- [ ] **Step 2: Verify red**

Run:

```bash
python3 -m unittest tests.test_ai_processor_prompt tests.test_wrong_question_library_pdf -v
```

Expected: FAIL because the prompt and normalized payload do not expose `image_rotation_degrees`.

- [ ] **Step 3: Implement minimal recognition support**

Update the prompt return-field list and rules. In `_normalize_wrong_question_recognition_result()`, parse `image_rotation_degrees` with `int(...)`; keep the value only if it is one of `{0, 90, 180, 270}`, otherwise use `0`. Include the field in both geometry and non-geometry returned dicts.

- [ ] **Step 4: Verify green**

Run the same unittest command. Expected: PASS.

### Task 2: Persist Upload Rotation

**Files:**
- Modify: `lesson_manager.py`
- Modify: `wrong_question_upload_worker.py`
- Test: `tests/test_wechat_parent_upload_api.py`

- [ ] **Step 1: Write failing worker persistence test**

In `test_worker_processes_pending_wrong_question_upload_task`, make `recognized_payload()` return `image_rotation_degrees=90` and assert:

```python
self.assertEqual(record["image_rotation_degrees"], 90)
```

- [ ] **Step 2: Verify red**

Run:

```bash
python3 -m unittest tests.test_wechat_parent_upload_api.WechatParentUploadApiTestCase.test_worker_processes_pending_wrong_question_upload_task -v
```

Expected: FAIL because the record does not have `image_rotation_degrees`.

- [ ] **Step 3: Implement minimal persistence**

Add `image_rotation_degrees INTEGER NOT NULL DEFAULT 0` to `wrong_question_submissions`, ensure the column in migrations, accept `image_rotation_degrees` in `create_wechat_wrong_question_submission()`, store normalized allowed values, and select/serialize it with records. Pass `recognition.get("image_rotation_degrees")` from the worker in both success and failed fallback record creation.

- [ ] **Step 4: Verify green**

Run the same targeted unittest command. Expected: PASS.

### Task 3: Rotate Geometry Images For PDF

**Files:**
- Modify: `pdf_engine.py`
- Test: `tests/test_wrong_question_library_pdf.py`

- [ ] **Step 1: Write failing PDF rotation test**

Add a test that patches `urllib.request.urlopen` with a small non-square PNG, calls a helper through `_build_browser_wrong_question_library_records()` with `is_geometry=1` and `image_rotation_degrees=90`, decodes the resulting data URL, and verifies the rotated image dimensions are swapped.

- [ ] **Step 2: Verify red**

Run:

```bash
python3 -m unittest tests.test_wrong_question_library_pdf -v
```

Expected: FAIL because image bytes are fetched without rotation.

- [ ] **Step 3: Implement minimal PDF rotation**

Add a helper in `pdf_engine.py` that accepts image bytes and clockwise degrees. Use Pillow, already available through ReportLab dependencies, to `Image.open(BytesIO(...))`, convert to RGB/RGBA as needed, rotate counterclockwise by the clockwise degrees using `expand=True`, and save as PNG bytes. Use this helper when building geometry `image_data_url` and the ReportLab geometry image card.

- [ ] **Step 4: Verify green**

Run the same unittest command. Expected: PASS.

### Task 4: Final Proof And Commit

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run full temporary proof script**

Run a temporary script that executes:

```bash
python3 -m unittest tests.test_ai_processor_prompt tests.test_wrong_question_library_pdf tests.test_wechat_parent_upload_api -v
python3 -m py_compile ai_processor.py lesson_manager.py wrong_question_upload_worker.py pdf_engine.py
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 2: Update handoff**

Record the current status, completed work, remaining issues, next step, risks, and workspace state without adding a command log.

- [ ] **Step 3: Commit implementation**

```bash
git add ai_processor.py lesson_manager.py wrong_question_upload_worker.py pdf_engine.py tests/test_ai_processor_prompt.py tests/test_wrong_question_library_pdf.py tests/test_wechat_parent_upload_api.py handoff.md
git commit -m "fix: rotate parent wrong question images for pdf"
```
