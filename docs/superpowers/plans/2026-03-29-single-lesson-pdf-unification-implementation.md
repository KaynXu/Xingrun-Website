# Single Lesson PDF Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every single-lesson PDF entrypoint generate the same review-plan template currently produced by `review_plan_templates/generate_review_pdfs.py`, and remove the old single-lesson `pdf_engine.py` path.

**Architecture:** Extract a reusable parameterized render function from `review_plan_templates/generate_review_pdfs.py`, add a focused adapter module that converts the system `plan` format into that renderer's input, then switch both `app.py` and `lesson_manager.py` to call the new unified entrypoint. Keep non-single-lesson PDF logic in `pdf_engine.py`, but delete the old single-lesson entrypoint and related dead helpers once the new path is verified.

**Tech Stack:** Flask, SQLite, Python `unittest`, ReportLab

---

### Task 1: Lock The Target Behavior With Failing Single-Lesson PDF Tests

**Files:**
- Create: `tests/test_single_lesson_pdf_unification.py`
- Reference: `demo_plan.py`

- [ ] **Step 1: Write a failing unit test for the new unified single-lesson renderer module**

```python
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module
import config_runtime
import lesson_manager
from app import app
from demo_plan import DEMO_PLAN


class SingleLessonPdfUnificationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        lesson_manager.DB_PATH = self.base / "lessons.db"
        config_runtime.CFG_PATH = self.base / "config.json"
        config_runtime.write_file_config({})
        lesson_manager.init_db()
        self.client = app.test_client()

        self.original_pdf_dir = app_module.PDF_DIR
        self.original_upload_dir = app_module.UPLOAD_DIR
        app_module.PDF_DIR = self.base / "pdfs"
        app_module.UPLOAD_DIR = self.base / "uploads"
        app_module.PDF_DIR.mkdir(parents=True, exist_ok=True)
        app_module.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        app_module.PDF_DIR = self.original_pdf_dir
        app_module.UPLOAD_DIR = self.original_upload_dir
        self.temp_dir.cleanup()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Auth-Token": token}

    def owner_token(self) -> str:
        login = self.client.post(
            "/api/login",
            json={"username": "Kayn", "password": "xingrun2026"},
        )
        self.assertEqual(login.status_code, 200)
        return login.get_json()["token"]

    def test_generate_single_lesson_pdf_outputs_review_template_markers(self):
        from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf

        output_path = self.base / "single-lesson.pdf"
        result = generate_single_lesson_pdf(copy.deepcopy(DEMO_PLAN), str(output_path))

        self.assertEqual(Path(result), output_path.resolve())
        self.assertTrue(output_path.exists())
        pdf_text = output_path.read_bytes().decode("latin1", errors="ignore")
        self.assertIn("使用说明", pdf_text)
        self.assertIn("全课覆盖清单", pdf_text)
        self.assertIn("上课金句回顾", pdf_text)
        self.assertNotIn("学生填写版", pdf_text)

    def test_api_lessons_uses_review_template_generator(self):
        token = self.owner_token()

        with patch("app.has_api_key", return_value=True), \
             patch("ai_processor.parse_and_generate_plan", return_value=copy.deepcopy(DEMO_PLAN)), \
             patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf") as generate_pdf:
            generate_pdf.return_value = str(self.base / "api-review-plan.pdf")

            response = self.client.post(
                "/api/lessons",
                headers=self.auth_headers(token),
                json={
                    "date": "2026-03-29",
                    "subject": "数学",
                    "grade": "初二",
                    "topic": "一次函数",
                    "summary_text": "一次函数课堂总结",
                    "input_type": "text",
                },
            )

        self.assertEqual(response.status_code, 201)
        generate_pdf.assert_called_once()

    def test_cmd_add_uses_review_template_generator(self):
        import argparse

        with patch("ai_processor.parse_and_generate_plan", return_value=copy.deepcopy(DEMO_PLAN)), \
             patch("review_plan_templates.single_lesson_pdf.generate_single_lesson_pdf") as generate_pdf, \
             patch("lesson_manager._open_pdf"):
            generate_pdf.return_value = str(self.base / "cli-review-plan.pdf")
            args = argparse.Namespace(
                audio=None,
                file=None,
                text="一次函数课堂总结",
                date="2026-03-29",
                subject="数学",
                grade="初二",
                topic="一次函数",
                weak="斜率和截距容易混淆",
                no_open=True,
            )
            lesson_manager.cmd_add(args)

        generate_pdf.assert_called_once()
```

- [ ] **Step 2: Run the new targeted test file to verify it fails for the right reason**

Run: `/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_single_lesson_pdf_unification -v`

Expected: FAIL because `review_plan_templates.single_lesson_pdf` does not exist yet and `app.py` / `lesson_manager.py` still import `pdf_engine.generate_lesson_pdf`.

- [ ] **Step 3: Re-run after fixing any typo until the failure stays behavior-level**

Run: `/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_single_lesson_pdf_unification -v`

Expected: the failures remain import / wrong-call-site failures, not syntax or fixture setup errors.

- [ ] **Step 4: Commit the red test scaffold when it is stable**

```bash
git add tests/test_single_lesson_pdf_unification.py
git commit -m "test: lock single lesson pdf unification behavior"
```

### Task 2: Extract A Reusable Review-Template Renderer And Adapter Layer

**Files:**
- Modify: `review_plan_templates/generate_review_pdfs.py`
- Create: `review_plan_templates/single_lesson_pdf.py`
- Test: `tests/test_single_lesson_pdf_unification.py`

- [ ] **Step 1: Add a reusable parameterized render function to `review_plan_templates/generate_review_pdfs.py`**

```python
def render_review_plan_pdf(
    *,
    lesson: dict,
    days: list[dict],
    final_reminder_lines: list[str],
    output_path: str,
    variant_key: str = "cn",
    knowledge_sections: dict | None = None,
) -> str:
    register_fonts()
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=24 * mm,
        bottomMargin=16 * mm,
        title=lesson["title"],
    )
    canvas_maker = lambda *args, **kwargs: TrackingCanvas(*args, char_space=LETTER_SPACING, **kwargs)
    doc.build(
        build_story(
            styles,
            variant_key,
            lesson=lesson,
            days=days,
            final_reminder_lines=final_reminder_lines,
            knowledge_sections=knowledge_sections or {},
        ),
        onFirstPage=on_page(styles, variant_key, lesson["title"]),
        onLaterPages=on_page(styles, variant_key, lesson["title"]),
        canvasmaker=canvas_maker,
    )
    return str(Path(output_path).resolve())
```

- [ ] **Step 2: Thread explicit parameters through `build_story` and `on_page` instead of relying on mutable module globals**

```python
def on_page(styles, variant_key, lesson_title):
    chinese_only = is_chinese_only(variant_key)
    labels = build_labels(chinese_only)

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(styles["accent"])
        canvas.setLineWidth(1)
        canvas.line(doc.leftMargin, A4[1] - 18 * mm, A4[0] - doc.rightMargin, A4[1] - 18 * mm)
        canvas.setFont("STSong-Light", 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(doc.leftMargin, 10 * mm, lesson_title)
        canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, labels["footer_right"].format(page=canvas.getPageNumber()))
        canvas.restoreState()

    return draw


def build_story(styles, variant_key, *, lesson, days, final_reminder_lines, knowledge_sections):
    base_date = date.today()
    variant = VARIANTS[variant_key]
    chinese_only = is_chinese_only(variant_key)
    labels = build_labels(chinese_only)
    story = []
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(lesson["title"], styles["title"]))
    subtitle = "" if chinese_only else lesson.get("subtitle", "")
    ...
    for index, day in enumerate(days):
        ...
        knowledge_items = knowledge_sections.get(day["day"], [])
        ...
    story.append(make_box(labels["final_reminder_box"], bullet_paragraph(localize_lines(final_reminder_lines, chinese_only), styles["body"]), styles, styles["soft"]))
    ...
```

- [ ] **Step 3: Create a focused adapter module for system `plan` -> review-template payload conversion**

```python
from pathlib import Path

from review_plan_templates.generate_review_pdfs import render_review_plan_pdf


DEFAULT_FINAL_REMINDERS = [
    "每一个复习日都要完整复习整节课内容。",
    "先回忆课堂原话，再完成当天填空与选择。",
    "遇到不会的题先回看课堂总结，再补做口头复述。",
]


def adapt_plan_to_review_template(plan_data: dict) -> tuple[dict, list[dict], list[str]]:
    lesson_info = plan_data.get("lesson_info", {})
    lesson = {
        "title": f"{lesson_info.get('topic') or '课后'}复习计划",
        "subtitle": "",
        "audience": "老师发给学生使用",
        "duration": "每次 10-20 分钟",
        "core_points": [plan_data.get("weak_points_summary", "")] if plan_data.get("weak_points_summary") else [],
        "full_review_topics": lesson_info.get("key_categories", []) or [lesson_info.get("topic") or "本课核心内容"],
        "quotes": collect_plan_quotes(plan_data),
    }
    days = [adapt_day(day_data) for day_data in plan_data.get("days", [])]
    reminders = list(DEFAULT_FINAL_REMINDERS)
    return lesson, days, reminders


def generate_single_lesson_pdf(plan_data: dict, output_path: str) -> str:
    lesson, days, reminders = adapt_plan_to_review_template(plan_data)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    return render_review_plan_pdf(
        lesson=lesson,
        days=days,
        final_reminder_lines=reminders,
        output_path=output_path,
        variant_key="cn",
        knowledge_sections={},
    )
```

- [ ] **Step 4: Run the targeted tests to make the new renderer green**

Run: `/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_single_lesson_pdf_unification -v`

Expected: `test_generate_single_lesson_pdf_outputs_review_template_markers` passes; the app and CLI call-site tests still fail because those entrypoints still point at `pdf_engine.generate_lesson_pdf`.

- [ ] **Step 5: Commit the reusable renderer and adapter layer**

```bash
git add review_plan_templates/generate_review_pdfs.py review_plan_templates/single_lesson_pdf.py tests/test_single_lesson_pdf_unification.py
git commit -m "feat: add unified single lesson review pdf renderer"
```

### Task 3: Switch The Web And CLI Single-Lesson Entry Points To The New Renderer

**Files:**
- Modify: `app.py`
- Modify: `lesson_manager.py`
- Test: `tests/test_single_lesson_pdf_unification.py`

- [ ] **Step 1: Replace the web single-lesson PDF import in `app.py`**

```python
    try:
        from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf
        safe = (topic or "课程").replace("/", "-").replace(" ", "_")[:28]
        pdf_name = f"{lesson_date}_{subject}_{safe}.pdf"
        pdf_path = str(PDF_DIR / pdf_name)
        generate_single_lesson_pdf(plan, pdf_path)
    except Exception as e:
        flash(f"PDF 生成失败：{e}", "error")
```

- [ ] **Step 2: Replace the CLI/store single-lesson PDF import in `lesson_manager.py`**

```python
    from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf
    safe_topic = topic.replace("/", "-").replace(" ", "_")[:30] if topic else "课程"
    pdf_name = f"{lesson_date}_{subject}_{safe_topic}.pdf"
    pdf_path = str(PDF_DIR / pdf_name)
    generate_single_lesson_pdf(plan, pdf_path)
    print(f"PDF 已生成：{pdf_path}")
```

- [ ] **Step 3: Run the targeted test file again to make the entrypoint regression tests pass**

Run: `/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_single_lesson_pdf_unification -v`

Expected: all three tests in `tests.test_single_lesson_pdf_unification` pass.

- [ ] **Step 4: Commit the call-site switch**

```bash
git add app.py lesson_manager.py tests/test_single_lesson_pdf_unification.py
git commit -m "feat: route single lesson pdf generation to review template"
```

### Task 4: Remove The Legacy Single-Lesson `pdf_engine.py` Path Without Touching Monthly PDFs

**Files:**
- Modify: `tests/test_single_lesson_pdf_unification.py`
- Modify: `pdf_engine.py`
- Modify: `README.md`

- [ ] **Step 1: Add a failing source-level regression test that locks removal of the old single-lesson entrypoint**

```python
    def test_legacy_single_lesson_entrypoint_removed_from_pdf_engine(self):
        source = (ROOT / "pdf_engine.py").read_text(encoding="utf-8")
        self.assertNotIn("def generate_lesson_pdf(", source)
```

- [ ] **Step 2: Run the targeted tests to verify the new removal assertion fails before cleanup**

Run: `/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_single_lesson_pdf_unification -v`

Expected: FAIL only on `test_legacy_single_lesson_entrypoint_removed_from_pdf_engine` because `pdf_engine.py` still defines the old single-lesson entrypoint.

- [ ] **Step 3: Delete the legacy single-lesson renderer from `pdf_engine.py`, but keep monthly/aggregate functions intact**

```python
# Remove the old single-lesson entrypoint block:
def generate_lesson_pdf(plan_data: dict, output_path: str,
                        show_quiz_answers: bool = False,
                        show_fill_answers: bool = False) -> str:
    ...

# Remove any helper functions used only by that block, but keep:
# - generate_monthly_pdf(...)
# - generate_weekly_pdf(...)
# - helper functions still referenced by monthly/aggregate PDF code
```

- [ ] **Step 4: Update the README so the single-lesson default path is documented correctly**

```markdown
- 网页和 CLI 的单课 PDF 现在统一走 `review_plan_templates/single_lesson_pdf.py`
- `review_plan_templates/generate_review_pdfs.py` 仍可独立生成同款版式 PDF
- `pdf_engine.py` 仅保留月度 / 非单课 PDF 逻辑
```

- [ ] **Step 5: Run the targeted tests again to verify legacy removal is complete**

Run: `/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_single_lesson_pdf_unification -v`

Expected: PASS; no legacy single-lesson `pdf_engine.generate_lesson_pdf` definition remains.

- [ ] **Step 6: Commit the cleanup**

```bash
git add pdf_engine.py README.md tests/test_single_lesson_pdf_unification.py
git commit -m "refactor: remove legacy single lesson pdf engine path"
```

### Task 5: Run Full Verification And Produce A Human-Readable Proof PDF

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run the focused backend regression suites**

Run: `/Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_single_lesson_pdf_unification tests.test_account_flow -v`

Expected: PASS, with the new unification tests and the existing account-flow suite both green.

- [ ] **Step 2: Generate one fresh single-lesson PDF through the unified renderer for visual proof**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python - <<'PY'
import copy
from pathlib import Path
from demo_plan import DEMO_PLAN
from review_plan_templates.single_lesson_pdf import generate_single_lesson_pdf

output = Path('review_plan_templates/pdf_output/_proof_single_lesson_unified.pdf')
generate_single_lesson_pdf(copy.deepcopy(DEMO_PLAN), str(output))
print(output.resolve())
PY`

Expected: prints an absolute PDF path under `review_plan_templates/pdf_output/` and the file opens with the same first-page card layout the user already approved.

- [ ] **Step 3: Open the generated proof PDF locally for final visual confirmation**

Run: `open /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/review_plan_templates/pdf_output/_proof_single_lesson_unified.pdf`

Expected: the first page shows the approved `使用说明 / 全课覆盖清单 / 上课金句回顾` layout.

- [ ] **Step 4: Update handoff with the switch, proof path, and verification results**

```markdown
- 单课 PDF 已统一切到 `review_plan_templates/single_lesson_pdf.py`
- 网页与 CLI 均不再调用旧 `pdf_engine.generate_lesson_pdf(...)`
- proof 文件：`review_plan_templates/pdf_output/_proof_single_lesson_unified.pdf`
- 验证：`tests.test_single_lesson_pdf_unification`、`tests.test_account_flow` 均通过
```

- [ ] **Step 5: Commit the verification note if `handoff.md` changes are kept in repo workflow, otherwise leave it outside git**

```bash
git add handoff.md
git commit -m "docs: record single lesson pdf unification proof"
```