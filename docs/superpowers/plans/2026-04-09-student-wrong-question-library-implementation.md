# Student Wrong Question Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn local WeChat wrong-question uploads into a student-scoped persistent PDF library where non-geometry questions must pass AI text extraction before admission, geometry questions are stored as image-first pages, and teachers can edit recognized question text from the web workspace.

**Architecture:** The website backend remains the source of truth. `wrong_question_submissions` gains recognition and student-library metadata, `app.py` turns WeChat upload into a synchronous “recognize then admit” flow, `ai_processor.py` adds a focused recognition helper, and `pdf_engine.py` generates one stable student-library PDF per student by rebuilding the same file path from all active recognized local records. The web `智能错题` page surfaces recognized question text for local WeChat records and lets teachers edit it; successful edits atomically rebuild the same student PDF.

**Tech Stack:** Flask, SQLite, Python `unittest`, ReportLab, React, Vite, `tsx --test`

---

## File Map

- Modify: `lesson_manager.py`
  - Add recognition/library columns, student-library query helpers, and atomic persistence helpers for create/edit + PDF path updates.
- Modify: `app.py`
  - Gate WeChat upload on AI recognition success, add student-library read endpoint, and extend local review save to edit `question_text`.
- Modify: `ai_processor.py`
  - Add a dedicated wrong-question recognition helper with geometry classification + text extraction.
- Modify: `pdf_engine.py`
  - Add student wrong-question library PDF generation.
- Modify: `frontend/src/smartWrongQuestions.ts`
  - Extend local record typing for recognition fields and library metadata.
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
  - Show recognized question text and teacher edit controls for local records.
- Create: `tests/test_wrong_question_library_pdf.py`
  - Validate PDF generator creates non-empty library PDFs.
- Modify: `tests/test_wechat_parent_upload_data.py`
  - Cover new persistence columns and helper behavior.
- Modify: `tests/test_wechat_parent_upload_api.py`
  - Cover recognition success/failure, geometry admission, and student library endpoint.
- Modify: `tests/test_smart_wrong_questions_api.py`
  - Cover local detail payload and teacher editing of `question_text`.
- Modify: `frontend/src/smart-wrong-questions.test.ts`
  - Cover new local detail UI and teacher save payload.

### Task 1: Persist Recognition And Student Library Metadata

**Files:**
- Modify: `lesson_manager.py`
- Modify: `tests/test_wechat_parent_upload_data.py`

- [ ] **Step 1: Write the failing data-layer tests**

```python
def test_wrong_question_submission_stores_recognition_and_library_fields(self):
    account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
    binding = lesson_manager.bind_parent_to_student(
        parent_wechat_account_id=account["id"],
        class_id=self.class_id,
        student_id=self.student["id"],
    )

    submission = lesson_manager.create_wechat_wrong_question_submission(
        binding_id=binding["id"],
        image_url="https://files.example.com/wrong-question.png",
        parent_note="这题又错了",
        recognition_status="recognized",
        is_geometry=False,
        question_text="计算 $2+3\times4$ 的结果。",
        question_text_source="ai",
        student_library_pdf_path="/tmp/student-1.pdf",
    )

    self.assertEqual(submission["recognition_status"], "recognized")
    self.assertEqual(submission["is_geometry"], 0)
    self.assertEqual(submission["question_text"], "计算 $2+3\\times4$ 的结果。")
    self.assertEqual(submission["question_text_source"], "ai")
    self.assertEqual(submission["student_library_pdf_path"], "/tmp/student-1.pdf")


def test_update_local_question_text_marks_teacher_source(self):
    account = lesson_manager.upsert_parent_wechat_account(openid="openid-parent-1")
    binding = lesson_manager.bind_parent_to_student(
        parent_wechat_account_id=account["id"],
        class_id=self.class_id,
        student_id=self.student["id"],
    )
    submission = lesson_manager.create_wechat_wrong_question_submission(
        binding_id=binding["id"],
        image_url="https://files.example.com/wrong-question.png",
        recognition_status="recognized",
        is_geometry=False,
        question_text="原始 AI 文本",
        question_text_source="ai",
    )

    updated = lesson_manager.update_wechat_wrong_question_question_text(
        submission["id"],
        question_text="老师修正后的题目文本",
        student_library_pdf_path="/tmp/student-1.pdf",
    )

    self.assertEqual(updated["question_text"], "老师修正后的题目文本")
    self.assertEqual(updated["question_text_source"], "teacher")
    self.assertEqual(updated["question_text_edited"], 1)
    self.assertEqual(updated["student_library_pdf_path"], "/tmp/student-1.pdf")
```

- [ ] **Step 2: Run the storage tests to verify they fail**

Run:

```bash
tmp_script="/tmp/xingrun-student-wq-store-red-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
/usr/bin/python3 -m unittest tests.test_wechat_parent_upload_data -v
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: `TypeError` or `AttributeError` because `create_wechat_wrong_question_submission()` does not yet accept recognition fields and `update_wechat_wrong_question_question_text()` does not exist.

- [ ] **Step 3: Add schema columns and helpers in `lesson_manager.py`**

```python
def init_db():
    with get_conn() as conn:
        _ensure_column(conn, "wrong_question_submissions", "recognition_status", "TEXT NOT NULL DEFAULT 'pending'")
        _ensure_column(conn, "wrong_question_submissions", "is_geometry", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "wrong_question_submissions", "question_text", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "question_text_edited", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "wrong_question_submissions", "question_text_source", "TEXT NOT NULL DEFAULT 'ai'")
        _ensure_column(conn, "wrong_question_submissions", "recognition_error", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "wrong_question_submissions", "student_library_pdf_path", "TEXT NOT NULL DEFAULT ''")


def create_wechat_wrong_question_submission(..., recognition_status: str = "pending", is_geometry: bool = False, question_text: str = "", question_text_source: str = "ai", recognition_error: str = "", student_library_pdf_path: str = "") -> dict:
    conn.execute(
        """
        INSERT INTO wrong_question_submissions (
            ..., recognition_status, is_geometry, question_text,
            question_text_edited, question_text_source, recognition_error, student_library_pdf_path
        ) VALUES (?, ..., ?, ?, ?, 0, ?, ?, ?)
        """,
        (..., recognition_status, 1 if is_geometry else 0, question_text.strip(), question_text_source, recognition_error.strip(), student_library_pdf_path.strip()),
    )


def update_wechat_wrong_question_question_text(record_id: str, *, question_text: str, student_library_pdf_path: str) -> Optional[dict]:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET question_text=?,
                question_text_edited=1,
                question_text_source='teacher',
                student_library_pdf_path=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
            """,
            (question_text.strip(), student_library_pdf_path.strip(), record_id),
        )
        refreshed = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
    return _serialize_wechat_wrong_question_submission_row(refreshed)
```

- [ ] **Step 4: Run the storage tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
Ran ... tests in ...

OK
```

- [ ] **Step 5: Commit**

```bash
git add lesson_manager.py tests/test_wechat_parent_upload_data.py
git commit -m "feat: persist student wrong question library metadata"
```

### Task 2: Add Recognition Helper And Student Library PDF Generator

**Files:**
- Modify: `ai_processor.py`
- Modify: `pdf_engine.py`
- Create: `tests/test_wrong_question_library_pdf.py`

- [ ] **Step 1: Write the failing PDF and recognition tests**

```python
def test_generate_student_wrong_question_library_pdf_creates_non_empty_pdf(self):
    records = [
        {
            "student_name": "Alice",
            "class_display_name": "六年级 1 班",
            "teacher_display_name": "平台管理员",
            "created_at": "2026-04-09 10:00:00",
            "is_geometry": 0,
            "question_text": "计算 $2+3\\times4$ 的结果。",
            "image_url": "https://files.example.com/question-1.png",
            "parent_note": "总是忘记先乘后加",
            "teacher_comment": "下节课先复盘运算顺序",
        }
    ]
    output_path = self.base / "student-1.pdf"

    result = pdf_engine.generate_student_wrong_question_library_pdf(
        student_name="Alice",
        class_name="六年级 1 班",
        records=records,
        output_path=str(output_path),
    )

    self.assertEqual(result, str(output_path))
    self.assertTrue(output_path.exists())
    self.assertGreater(output_path.stat().st_size, 0)


def test_recognize_wrong_question_image_rejects_blank_non_geometry_text(self):
    with self.assertRaises(ValueError):
        ai_processor._normalize_wrong_question_recognition_result(
            {
                "is_geometry": False,
                "question_text": "无法识别",
                "confidence": "low",
                "notes": "图片模糊",
            }
        )
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
tmp_script="/tmp/xingrun-student-wq-pdf-red-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
/usr/bin/python3 -m unittest tests.test_wrong_question_library_pdf -v
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: `AttributeError` for missing `generate_student_wrong_question_library_pdf()` and missing recognition normalization helper.

- [ ] **Step 3: Add recognition helper and PDF generator**

```python
WRONG_QUESTION_RECOGNITION_PROMPT = """你要判断题图是否属于几何题/几何体题，并提取非几何题题目文本。只返回 JSON。"""


def _normalize_wrong_question_recognition_result(payload: dict) -> dict:
    is_geometry = bool(payload.get("is_geometry"))
    question_text = str(payload.get("question_text") or "").strip()
    if is_geometry:
        return {"is_geometry": True, "question_text": "", "confidence": str(payload.get("confidence") or ""), "notes": str(payload.get("notes") or "").strip()}
    if question_text in {"", "无法识别", "看不清", "题目缺失"} or len(question_text) < 6:
        raise ValueError("题目识别失败，请重新识别")
    return {"is_geometry": False, "question_text": question_text, "confidence": str(payload.get("confidence") or ""), "notes": str(payload.get("notes") or "").strip()}


def recognize_wrong_question_image(image_url: str) -> dict:
    client = _get_client()
    response = client.chat.completions.create(...)
    payload = json.loads(response.choices[0].message.content)
    return _normalize_wrong_question_recognition_result(payload)
```

```python
def generate_student_wrong_question_library_pdf(*, student_name: str, class_name: str, records: list[dict], output_path: str) -> str:
    _ensure_fonts()
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=1.6 * cm, bottomMargin=1.6 * cm)
    styles = _make_styles()
    story = [
        Paragraph(f"{html.escape(student_name)} 错题库", styles["title"]),
        Paragraph(f"班级：{html.escape(class_name)}", styles["meta"]),
        Spacer(1, 0.4 * cm),
    ]
    for index, record in enumerate(records, start=1):
        if index > 1:
            story.append(PageBreak())
        story.append(Paragraph(f"第 {index} 题", styles["section"]))
        if record.get("is_geometry"):
            story.append(Paragraph("几何题按图片入库", styles["body"]))
        else:
            story.append(Paragraph(html.escape(record.get("question_text") or ""), styles["body"]))
        story.append(Paragraph(f"家长备注：{html.escape(record.get('parent_note') or '无')}", styles["body"]))
        story.append(Paragraph(f"老师备注：{html.escape(record.get('teacher_comment') or '无')}", styles["body"]))
    doc.build(story)
    return output_path
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
Ran ... tests in ...

OK
```

- [ ] **Step 5: Commit**

```bash
git add ai_processor.py pdf_engine.py tests/test_wrong_question_library_pdf.py
git commit -m "feat: add recognition and student library pdf generation"
```

### Task 3: Gate WeChat Upload On Recognition And Expose Student Library Endpoint

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Modify: `tests/test_wechat_parent_upload_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
@patch("app._rebuild_student_wrong_question_library")
@patch("app.ai_processor.recognize_wrong_question_image")
def test_wechat_upload_requires_successful_non_geometry_recognition(self, recognize_wrong_question_image, rebuild_library):
    recognize_wrong_question_image.return_value = {
        "is_geometry": False,
        "question_text": "计算 $2+3\\times4$ 的结果。",
        "confidence": "high",
        "notes": "",
    }
    rebuild_library.return_value = "/tmp/student-1.pdf"

    response = self.client.post("/api/wechat/wrong-questions", headers=self.service_headers(), json={...})

    self.assertEqual(response.status_code, 201)
    record = response.get_json()["record"]
    self.assertEqual(record["recognition_status"], "recognized")
    self.assertEqual(record["question_text"], "计算 $2+3\\times4$ 的结果。")
    self.assertEqual(record["student_library_pdf_path"], "/tmp/student-1.pdf")


@patch("app.ai_processor.recognize_wrong_question_image", side_effect=ValueError("题目识别失败，请重新识别"))
def test_wechat_upload_rejects_failed_non_geometry_recognition(self, _recognize_wrong_question_image):
    response = self.client.post("/api/wechat/wrong-questions", headers=self.service_headers(), json={...})
    self.assertEqual(response.status_code, 422)
    self.assertEqual(response.get_json()["error"], "题目识别失败，请重新识别")
    self.assertEqual(lesson_manager.list_wechat_wrong_question_submissions(), [])


@patch("app._rebuild_student_wrong_question_library")
@patch("app.ai_processor.recognize_wrong_question_image")
def test_wechat_child_library_endpoint_returns_shared_pdf_url(self, recognize_wrong_question_image, rebuild_library):
    recognize_wrong_question_image.return_value = {"is_geometry": True, "question_text": "", "confidence": "high", "notes": "几何图形题"}
    rebuild_library.return_value = "/tmp/student-1.pdf"
    ...
    response = self.client.get(f"/api/wechat/children/{self.student['id']}/wrong-question-library", headers=self.service_headers(), query_string={"open_id": "openid-1"})
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.get_json()["pdf_url"], "/api/wechat/student-libraries/1")
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run:

```bash
tmp_script="/tmp/xingrun-student-wq-api-red-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
/usr/bin/python3 -m unittest tests.test_wechat_parent_upload_api -v
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: FAIL because upload route writes records directly without recognition gating and the library endpoint does not exist.

- [ ] **Step 3: Implement upload gating and student-library routes in `app.py`**

```python
def _student_wrong_question_library_path(student_id: int) -> Path:
    library_dir = PDF_DIR / "wrong_question_libraries"
    library_dir.mkdir(parents=True, exist_ok=True)
    return library_dir / f"student-{student_id}.pdf"


def _rebuild_student_wrong_question_library(student_id: int) -> str:
    records = lesson_manager.list_student_wrong_question_library_records(student_id)
    if not records:
        raise ValueError("student wrong question library has no records")
    output_path = _student_wrong_question_library_path(student_id)
    return pdf_engine.generate_student_wrong_question_library_pdf(
        student_name=records[0]["student_name"],
        class_name=records[0]["class_display_name"],
        records=records,
        output_path=str(output_path),
    )


@app.route("/api/wechat/wrong-questions", methods=["POST"])
def api_wechat_wrong_questions_create():
    ...
    recognition = ai_processor.recognize_wrong_question_image(image_url)
    record = create_wechat_wrong_question_submission(..., recognition_status="recognized", is_geometry=recognition["is_geometry"], question_text=recognition["question_text"], question_text_source="ai")
    pdf_path = _rebuild_student_wrong_question_library(binding["student_id"])
    record = lesson_manager.attach_student_library_pdf_path(record["id"], pdf_path)
    return jsonify({"record": record, "student_library_pdf_url": f"/api/wechat/student-libraries/{binding['student_id']}"}), 201


@app.route("/api/wechat/children/<int:student_id>/wrong-question-library", methods=["GET"])
def api_wechat_child_wrong_question_library(student_id):
    ...
    return jsonify({
        "student_id": student_id,
        "pdf_url": f"/api/wechat/student-libraries/{student_id}",
        "updated_at": items[0].get("updated_at") if items else "",
        "total_items": len(items),
    })


@app.route("/api/wechat/student-libraries/<int:student_id>", methods=["GET"])
def api_wechat_student_library_pdf(student_id):
    ...
    return send_file(pdf_path, mimetype="application/pdf", download_name=Path(pdf_path).name)
```

- [ ] **Step 4: Run the API tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
Ran ... tests in ...

OK
```

- [ ] **Step 5: Commit**

```bash
git add app.py lesson_manager.py tests/test_wechat_parent_upload_api.py
git commit -m "feat: require recognition before wrong question admission"
```

### Task 4: Let Teachers Edit Local Question Text And Rebuild The Library

**Files:**
- Modify: `app.py`
- Modify: `tests/test_smart_wrong_questions_api.py`

- [ ] **Step 1: Write the failing local-review API tests**

```python
@patch("app._rebuild_student_wrong_question_library")
def test_local_wrong_question_review_can_update_question_text(self, rebuild_library):
    rebuild_library.return_value = "/tmp/student-1.pdf"
    record = self.create_local_wechat_record(self.owner_payload["user"]["id"])
    with lesson_manager.get_conn() as conn:
        conn.execute(
            "UPDATE wrong_question_submissions SET recognition_status='recognized', question_text='原始 AI 文本', question_text_source='ai' WHERE id=?",
            (record["id"],),
        )

    response = self.client.put(
        f"/api/wrong-questions/{record['id']}/review",
        headers=self.auth_headers(self.owner_payload["token"]),
        json={"teacher_comment": "老师备注", "status": "reviewed", "question_text": "老师修正后的题目文本"},
    )

    self.assertEqual(response.status_code, 200)
    saved = response.get_json()["record"]
    self.assertEqual(saved["question_text"], "老师修正后的题目文本")
    self.assertEqual(saved["question_text_source"], "teacher")
    self.assertEqual(saved["student_library_pdf_path"], "/tmp/student-1.pdf")
```

- [ ] **Step 2: Run the local-review tests to verify they fail**

Run:

```bash
tmp_script="/tmp/xingrun-student-wq-review-red-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
/usr/bin/python3 -m unittest tests.test_smart_wrong_questions_api -v
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: FAIL because local review save ignores `question_text` and does not rebuild the student library PDF.

- [ ] **Step 3: Extend local review save path in `app.py`**

```python
@app.route("/api/wrong-questions/<record_id>/review", methods=["PUT"])
def api_wrong_question_review_save(record_id):
    ...
    if local_record:
        question_text = str((request.json or {}).get("question_text") or "").strip()
        saved_record = save_wechat_wrong_question_review(record_id, request.json or {})
        if question_text and not local_record.get("is_geometry"):
            pdf_path = _rebuild_student_wrong_question_library(local_record["student_id"])
            saved_record = lesson_manager.update_wechat_wrong_question_question_text(
                record_id,
                question_text=question_text,
                student_library_pdf_path=pdf_path,
            )
        return jsonify({"ok": True, "record": saved_record})
```

- [ ] **Step 4: Run the local-review tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
Ran ... tests in ...

OK
```

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_smart_wrong_questions_api.py
git commit -m "feat: let teachers edit local wrong question text"
```

### Task 5: Surface Question Text Editing In The Web Workspace

**Files:**
- Modify: `frontend/src/smartWrongQuestions.ts`
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
- Modify: `frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Write the failing frontend tests**

```typescript
test('normalizeWrongQuestionRecord keeps local recognition fields', () => {
  const normalized = normalizeWrongQuestionRecord({
    id: 'wechat-record-1',
    source: 'wechat_mp',
    recognition_status: 'recognized',
    is_geometry: 0,
    question_text: '计算 2+3×4 的结果。',
    question_text_source: 'ai',
    student_library_pdf_path: '/api/wechat/student-libraries/1',
  });

  assert.equal(normalized.recognitionStatus, 'recognized');
  assert.equal(normalized.isGeometry, false);
  assert.equal(normalized.questionText, '计算 2+3×4 的结果。');
  assert.equal(normalized.studentLibraryPdfPath, '/api/wechat/student-libraries/1');
});


test('SmartWrongQuestionsPage lets teachers edit local non-geometry question text', async () => {
  ...
  assert.match(domEnvironment.container.textContent || '', /题目文本/);
  const textarea = domEnvironment.container.querySelector('textarea[placeholder="填写可直接进入错题库 PDF 的题目文本"]') as HTMLTextAreaElement | null;
  assert.ok(textarea instanceof HTMLTextAreaElement);
  assert.equal(textarea.value, '原始 AI 文本');
  ...
  const payload = JSON.parse(String(saveCall?.init?.body));
  assert.equal(payload.question_text, '老师修正后的题目文本');
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run:

```bash
tmp_script="/tmp/xingrun-student-wq-frontend-red-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/smart-wrong-questions.test.ts
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: FAIL because the normalized local record shape lacks recognition fields and the page has no editable question-text control.

- [ ] **Step 3: Extend types and local detail UI**

```typescript
export interface WrongQuestionRecord {
  ...
  recognitionStatus: string;
  isGeometry: boolean;
  questionText: string;
  questionTextSource: string;
  studentLibraryPdfPath: string;
}

export function normalizeWrongQuestionRecord(rawRecord: unknown, fallbackIndex = 0): WrongQuestionRecord {
  ...
  recognitionStatus: pickStringValue(source, ['recognitionStatus', 'recognition_status']) || 'pending',
  isGeometry: pickNumberValue(source, ['isGeometry', 'is_geometry']) === 1,
  questionText: pickStringValue(source, ['questionText', 'question_text']),
  questionTextSource: pickStringValue(source, ['questionTextSource', 'question_text_source']) || 'ai',
  studentLibraryPdfPath: pickStringValue(source, ['studentLibraryPdfPath', 'student_library_pdf_path']),
}
```

```tsx
{selectedRecord?.source === 'wechat_mp' && !selectedRecord.isGeometry ? (
  <label className="space-y-2 text-sm text-slate-600">
    <span>题目文本</span>
    <textarea
      className={workspaceFieldClass}
      placeholder="填写可直接进入错题库 PDF 的题目文本"
      value={selectedDraft?.questionText ?? selectedRecord.questionText}
      onChange={(event) => handleDraftChange('questionText', event.target.value)}
    />
  </label>
) : null}
```

- [ ] **Step 4: Run the frontend tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
pass ...
fail 0
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/smartWrongQuestions.ts frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: edit local wrong question text from workspace"
```

### Task 6: Run Focused Regression Proof

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run the backend proof script**

Run:

```bash
tmp_script="/tmp/xingrun-student-wq-backend-proof-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
/usr/bin/python3 -m unittest \
  tests.test_wechat_parent_upload_data \
  tests.test_wechat_parent_upload_api \
  tests.test_smart_wrong_questions_api \
  tests.test_wrong_question_library_pdf -v
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected:

```text
Ran ... tests in ...

OK
```

- [ ] **Step 2: Run the frontend proof script**

Run:

```bash
tmp_script="/tmp/xingrun-student-wq-frontend-proof-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/smart-wrong-questions.test.ts
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected:

```text
pass ...
fail 0
```

- [ ] **Step 3: Update handoff with result and proof paths**

```markdown
## 智能错题学生级错题库实现完成（2026-04-09）

### 已完成
- 本地微信错题上传改为“先识别，后入库”
- 非几何题识别失败会阻止入库
- 几何题按图片页进入学生错题库
- 每个学生固定一个错题库 PDF 路径
- 网页端老师可修改题目文本并触发 PDF 重建

### proof
- Backend: `/tmp/xingrun-student-wq-backend-proof-20260409.sh`
- Frontend: `/tmp/xingrun-student-wq-frontend-proof-20260409.sh`
```

- [ ] **Step 4: Commit**

```bash
git add handoff.md
git commit -m "docs: record student wrong question library rollout"
```