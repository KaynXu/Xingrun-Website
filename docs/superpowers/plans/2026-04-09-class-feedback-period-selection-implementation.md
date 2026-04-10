# Class Feedback Period Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace freeform class-feedback date-range creation with explicit daily, weekly, monthly, and stage period modes that save normalized period labels while preserving derived date ranges for lesson matching.

**Architecture:** Keep `class_feedback_tasks` as the only task record, but expand it to store both business semantics (`period_granularity`, `period_label`) and operational range (`start_date`, `end_date`, `period_length_days`). Backend remains the source of truth for deriving labels and date windows, while the React page mirrors the same rules for preview, lesson counting, and task creation UI.

**Tech Stack:** Flask, SQLite, Python `unittest`, React, TypeScript, `tsx --test`, Vite

---

## File Map

- Modify: `lesson_manager.py`
  - Add normalized period-label derivation, explicit mode resolution, schema migration for `period_label`, and legacy `custom` compatibility.
- Modify: `app.py`
  - Accept structured period payloads for class-feedback task creation and return normalized task metadata.
- Modify: `tests/test_class_feedback_store.py`
  - Cover daily/weekly/monthly/stage derivation, normalized labels, legacy `custom` compatibility, and same-granularity lookup behavior.
- Modify: `tests/test_class_feedback_api.py`
  - Cover structured create payloads and API response shape for normalized period labels.
- Modify: `tests/test_organization_rooted_db_structure.py`
  - Cover the new `period_label` column on `class_feedback_tasks`.
- Modify: `frontend/src/classFeedbackGeneration.ts`
  - Add explicit period-mode types, preview helpers, normalized payload builder, and task type updates.
- Modify: `frontend/src/App.tsx`
  - Replace raw start/end date inputs with period-mode selectors and derived-preview state.
- Modify: `frontend/src/ClassFeedbackGenerationWorkspace.tsx`
  - Surface normalized period label and derived range summary in the workspace header.
- Modify: `frontend/src/class-feedback-generation.test.tsx`
  - Cover helper output, control-bar source assertions, and normalized summary display.
- Modify: `handoff.md`
  - Record completed implementation and proof after code changes land.

### Task 1: Add Period Label Storage And Store-Level Derivation

**Files:**
- Modify: `tests/test_class_feedback_store.py`
- Modify: `tests/test_organization_rooted_db_structure.py`
- Modify: `lesson_manager.py`

- [ ] **Step 1: Write the failing store and schema tests**

Add these tests to `tests/test_class_feedback_store.py`:

```python
    def test_create_task_normalizes_daily_weekly_monthly_and_stage_labels(self):
        owner = self._owner()
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])

        daily_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            created_by=owner["id"],
            period_granularity="daily",
            anchor_date="2026-04-09",
        )
        weekly_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            created_by=owner["id"],
            period_granularity="weekly",
            year=2026,
            week=15,
        )
        monthly_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            created_by=owner["id"],
            period_granularity="monthly",
            year=2026,
            month=3,
        )
        stage_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            created_by=owner["id"],
            period_granularity="stage",
            year=2026,
            stage_name="秋季",
        )

        self.assertEqual((daily_task["period_granularity"], daily_task["period_label"]), ("daily", "2026-04-09"))
        self.assertEqual((weekly_task["period_granularity"], weekly_task["period_label"]), ("weekly", "2026第15周"))
        self.assertEqual((monthly_task["period_granularity"], monthly_task["period_label"]), ("monthly", "2026三月"))
        self.assertEqual((stage_task["period_granularity"], stage_task["period_label"]), ("stage", "2026秋季"))
        self.assertEqual((stage_task["start_date"], stage_task["end_date"]), ("2026-09-01", "2027-01-31"))

    def test_create_task_keeps_legacy_date_range_callers_and_marks_custom(self):
        owner = self._owner()
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])

        task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            start_date="2026-04-02",
            end_date="2026-04-05",
            created_by=owner["id"],
        )

        self.assertEqual(task["period_granularity"], "custom")
        self.assertEqual(task["period_label"], "2026-04-02至2026-04-05")

    def test_previous_confirmed_entry_prefers_same_granularity_before_falling_back(self):
        owner = self._owner()
        class_id = lesson_manager.save_class("S01A1", subject="英语", grade="六年级")
        lesson_manager.set_class_teacher_user_id(class_id, owner["id"])
        student = lesson_manager.create_student_for_class(class_id, "张三")

        monthly_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            created_by=owner["id"],
            period_granularity="monthly",
            year=2026,
            month=3,
        )
        lesson_manager.save_class_feedback_generation_result(
            monthly_task["id"],
            class_summary_ai_draft="月反馈草稿",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "月反馈草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            monthly_task["id"],
            class_summary_final_text="月反馈终稿",
            student_entries=[{"student_id": student["id"], "final_text": "月反馈终稿", "checked_at": "2026-03-31 20:00:00"}],
        )

        weekly_task = lesson_manager.create_class_feedback_task(
            class_id=class_id,
            teacher_user_id=owner["id"],
            teacher_name_snapshot=owner["display_name"],
            created_by=owner["id"],
            period_granularity="weekly",
            year=2026,
            week=15,
        )
        lesson_manager.save_class_feedback_generation_result(
            weekly_task["id"],
            class_summary_ai_draft="周反馈草稿",
            student_entries=[{"student_id": student["id"], "name": "张三", "ai_draft": "周反馈草稿"}],
        )
        lesson_manager.confirm_class_feedback_task(
            weekly_task["id"],
            class_summary_final_text="周反馈终稿",
            student_entries=[{"student_id": student["id"], "final_text": "周反馈终稿", "checked_at": "2026-04-12 20:00:00"}],
        )

        self.assertEqual(
            lesson_manager.find_previous_confirmed_class_feedback_entry(
                class_id=class_id,
                student_id=student["id"],
                period_granularity="weekly",
                before_end_date="2026-04-30",
            )["final_text"],
            "周反馈终稿",
        )
        self.assertEqual(
            lesson_manager.find_previous_confirmed_class_feedback_entry(
                class_id=class_id,
                student_id=student["id"],
                period_granularity="stage",
                before_end_date="2026-04-30",
            )["final_text"],
            "周反馈终稿",
        )
```

Add this schema assertion to `tests/test_organization_rooted_db_structure.py` inside the existing `class_feedback_tasks` table-info check:

```python
        self.assertIn("period_label", columns)
        self.assertEqual(columns["period_label"]["type"].upper(), "TEXT")
```

- [ ] **Step 2: Run the failing backend tests**

Run:

```bash
tmp_script="/tmp/xingrun-class-feedback-period-store-red-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
/usr/bin/python3 -m unittest tests.test_class_feedback_store tests.test_organization_rooted_db_structure -v
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: FAIL with `TypeError` because `create_class_feedback_task()` does not yet accept `period_granularity` / `anchor_date` / `year` / `week` / `month` / `stage_name`, and FAIL because `period_label` column does not exist.

- [ ] **Step 3: Write the minimal store implementation in `lesson_manager.py`**

Add the schema migration and the explicit period-resolution helpers:

```python
CLASS_FEEDBACK_MONTH_LABELS = {
    1: "一月",
    2: "二月",
    3: "三月",
    4: "四月",
    5: "五月",
    6: "六月",
    7: "七月",
    8: "八月",
    9: "九月",
    10: "十月",
    11: "十一月",
    12: "十二月",
}


def _format_class_feedback_legacy_period_label(start_date: str, end_date: str) -> str:
    if start_date == end_date:
        return start_date
    return f"{start_date}至{end_date}"


def _resolve_class_feedback_period_selection(
    *,
    period_granularity: str | None,
    start_date: str,
    end_date: str,
    anchor_date: str,
    year: int | None,
    week: int | None,
    month: int | None,
    stage_name: str,
) -> tuple[str, str, int, str, str]:
    if period_granularity in (None, ""):
        normalized_start = str(start_date or "").strip()
        normalized_end = str(end_date or "").strip()
        period_length_days, derived_granularity = _derive_class_feedback_period_fields(normalized_start, normalized_end)
        return (
            normalized_start,
            normalized_end,
            period_length_days,
            derived_granularity,
            _format_class_feedback_legacy_period_label(normalized_start, normalized_end),
        )

    if period_granularity == "daily":
        normalized_start = str(anchor_date or "").strip()
        normalized_end = normalized_start
        period_length_days = 1
        return normalized_start, normalized_end, period_length_days, "daily", normalized_start

    if period_granularity == "weekly":
        if year is None or week is None:
            raise ValueError("weekly period requires year and week")
        monday = datetime.fromisocalendar(year, week, 1).date()
        sunday = monday + timedelta(days=6)
        return monday.isoformat(), sunday.isoformat(), 7, "weekly", f"{year}第{week}周"

    if period_granularity == "monthly":
        if year is None or month is None or month not in CLASS_FEEDBACK_MONTH_LABELS:
            raise ValueError("monthly period requires valid year and month")
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        return first_day.isoformat(), last_day.isoformat(), (last_day - first_day).days + 1, "monthly", f"{year}{CLASS_FEEDBACK_MONTH_LABELS[month]}"

    if period_granularity == "stage":
        if year is None:
            raise ValueError("stage period requires year")
        if stage_name == "春季":
            stage_start, stage_end = date(year, 2, 1), date(year, 6, 30)
        elif stage_name == "暑假":
            stage_start, stage_end = date(year, 7, 1), date(year, 8, 31)
        elif stage_name == "秋季":
            stage_start, stage_end = date(year, 9, 1), date(year + 1, 1, 31)
        elif stage_name == "寒假":
            stage_start, stage_end = date(year, 1, 1), date(year, 2, calendar.monthrange(year, 2)[1])
        else:
            raise ValueError("stage period requires valid stage_name")
        return stage_start.isoformat(), stage_end.isoformat(), (stage_end - stage_start).days + 1, "stage", f"{year}{stage_name}"

    raise ValueError("unsupported class feedback period_granularity")
```

Update `init_db()` and task serialization/insert paths:

```python
        _ensure_column(conn, "class_feedback_tasks", "period_label", "TEXT NOT NULL DEFAULT ''")


def _serialize_class_feedback_task_row(row: sqlite3.Row, student_entries: Optional[list[dict]] = None) -> dict:
    task = dict(row)
    task["period_label"] = str(task.get("period_label") or "")
    ...


def create_class_feedback_task(
    *,
    class_id: int,
    teacher_user_id: Optional[int],
    teacher_name_snapshot: str,
    start_date: str = "",
    end_date: str = "",
    created_by: int,
    period_granularity: Optional[str] = None,
    anchor_date: str = "",
    year: Optional[int] = None,
    week: Optional[int] = None,
    month: Optional[int] = None,
    stage_name: str = "",
):
    resolved_start_date, resolved_end_date, period_length_days, resolved_granularity, period_label = _resolve_class_feedback_period_selection(
        period_granularity=period_granularity,
        start_date=start_date,
        end_date=end_date,
        anchor_date=anchor_date,
        year=year,
        week=week,
        month=month,
        stage_name=stage_name,
    )
    ...
            INSERT INTO class_feedback_tasks (
                organization_id, class_id, teacher_user_id, teacher_name_snapshot,
                start_date, end_date, period_length_days, period_granularity, period_label,
                status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
    ...
                resolved_start_date,
                resolved_end_date,
                period_length_days,
                resolved_granularity,
                period_label,
                created_by,
```

- [ ] **Step 4: Run the backend tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
Ran ... tests in ...s

OK
```

- [ ] **Step 5: Commit**

```bash
git add lesson_manager.py tests/test_class_feedback_store.py tests/test_organization_rooted_db_structure.py
git commit -m "feat: store normalized class feedback periods"
```

### Task 2: Accept Structured Period Payloads In The API

**Files:**
- Modify: `tests/test_class_feedback_api.py`
- Modify: `app.py`

- [ ] **Step 1: Write the failing API tests**

Add these tests to `tests/test_class_feedback_api.py`:

```python
    def test_create_task_accepts_weekly_payload_and_returns_period_label(self):
        class_id = lesson_manager.save_class("假期冲刺班", subject="英语", grade="六年级")
        lesson_manager.create_student_for_class(class_id, "张三")

        response = self.client.post(
            "/api/class-feedback/tasks",
            headers=self.headers,
            json={"class_id": class_id, "period_granularity": "weekly", "year": 2026, "week": 15},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["period_granularity"], "weekly")
        self.assertEqual(payload["period_label"], "2026第15周")
        self.assertEqual(payload["start_date"], "2026-04-06")
        self.assertEqual(payload["end_date"], "2026-04-12")

    def test_create_task_rejects_invalid_stage_payload(self):
        class_id = lesson_manager.save_class("假期冲刺班", subject="英语", grade="六年级")
        lesson_manager.create_student_for_class(class_id, "张三")

        response = self.client.post(
            "/api/class-feedback/tasks",
            headers=self.headers,
            json={"class_id": class_id, "period_granularity": "stage", "year": 2026, "stage_name": "春学期"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("stage_name", response.get_json()["error"])

    def test_create_task_keeps_legacy_start_and_end_payload_compatible(self):
        class_id = lesson_manager.save_class("假期冲刺班", subject="英语", grade="六年级")
        lesson_manager.create_student_for_class(class_id, "张三")

        response = self.client.post(
            "/api/class-feedback/tasks",
            headers=self.headers,
            json={"class_id": class_id, "start_date": "2026-07-12", "end_date": "2026-07-12"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["period_granularity"], "daily")
        self.assertEqual(payload["period_label"], "2026-07-12")
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run:

```bash
tmp_script="/tmp/xingrun-class-feedback-period-api-red-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
/usr/bin/python3 -m unittest tests.test_class_feedback_api -v
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: FAIL because `/api/class-feedback/tasks` ignores `period_granularity`, does not validate `stage_name`, and does not return `period_label`.

- [ ] **Step 3: Update `app.py` to normalize the create payload**

Replace the create-route extraction with structured payload handling while keeping legacy date compatibility:

```python
@app.route("/api/class-feedback/tasks", methods=["POST"])
def api_class_feedback_task_create():
    ...
    period_granularity = str(data.get("period_granularity") or "").strip() or None
    anchor_date = str(data.get("anchor_date") or "").strip()
    year = data.get("year")
    week = data.get("week")
    month = data.get("month")
    stage_name = str(data.get("stage_name") or "").strip()
    start_date = str(data.get("start_date") or "").strip()
    end_date = str(data.get("end_date") or "").strip()
    ...
    task = create_class_feedback_task(
        class_id=class_id,
        teacher_user_id=cls.get("teacher_user_id"),
        teacher_name_snapshot=teacher_name_snapshot,
        created_by=user["id"],
        period_granularity=period_granularity,
        anchor_date=anchor_date,
        year=year if isinstance(year, int) else None,
        week=week if isinstance(week, int) else None,
        month=month if isinstance(month, int) else None,
        stage_name=stage_name,
        start_date=start_date,
        end_date=end_date,
    )
    ...
```

Keep the route behavior the same otherwise: same auth checks, same teacher snapshot fallback, same `201` response.

- [ ] **Step 4: Run the API tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
Ran ... tests in ...s

OK
```

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_class_feedback_api.py
git commit -m "feat: accept structured class feedback periods"
```

### Task 3: Replace Freeform Date Inputs With Period Mode Controls In The Frontend

**Files:**
- Modify: `frontend/src/class-feedback-generation.test.tsx`
- Modify: `frontend/src/classFeedbackGeneration.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing frontend tests**

Add these helper and source assertions to `frontend/src/class-feedback-generation.test.tsx`:

```tsx
import {
  buildClassFeedbackConfirmPayload,
  buildClassFeedbackPeriodPreview,
  buildCreateClassFeedbackTaskRequest,
  defaultStageLabelGroups,
  formatClassFeedbackStudentCopyText,
  type ClassFeedbackStudentCard,
} from './classFeedbackGeneration';

test('buildClassFeedbackPeriodPreview derives normalized labels and ranges', () => {
  assert.deepEqual(buildClassFeedbackPeriodPreview({ periodGranularity: 'daily', anchorDate: '2026-04-09' }), {
    periodLabel: '2026-04-09',
    startDate: '2026-04-09',
    endDate: '2026-04-09',
  });
  assert.deepEqual(buildClassFeedbackPeriodPreview({ periodGranularity: 'weekly', year: 2026, week: 15 }), {
    periodLabel: '2026第15周',
    startDate: '2026-04-06',
    endDate: '2026-04-12',
  });
  assert.deepEqual(buildClassFeedbackPeriodPreview({ periodGranularity: 'monthly', year: 2026, month: 3 }), {
    periodLabel: '2026三月',
    startDate: '2026-03-01',
    endDate: '2026-03-31',
  });
  assert.deepEqual(buildClassFeedbackPeriodPreview({ periodGranularity: 'stage', year: 2026, stageName: '秋季' }), {
    periodLabel: '2026秋季',
    startDate: '2026-09-01',
    endDate: '2027-01-31',
  });
});

test('buildCreateClassFeedbackTaskRequest emits structured backend payloads', () => {
  assert.deepEqual(buildCreateClassFeedbackTaskRequest({ classId: 7, periodGranularity: 'weekly', year: 2026, week: 15 }), {
    class_id: 7,
    period_granularity: 'weekly',
    year: 2026,
    week: 15,
  });
});

test('App source replaces raw date range inputs with period-mode controls', () => {
  assert.match(appSource, /const \[classFeedbackPeriodGranularity, setClassFeedbackPeriodGranularity\] = useState/);
  assert.match(appSource, /buildClassFeedbackPeriodPreview\(/);
  assert.match(appSource, /period_granularity: payload\.periodGranularity/);
  assert.match(appSource, /反馈阶段：\$\{classFeedbackPeriodPreview\.periodLabel\}/);
  assert.doesNotMatch(appSource, /type="date"\s*value=\{startDate\}/);
  assert.doesNotMatch(appSource, /type="date"\s*value=\{endDate\}/);
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run:

```bash
tmp_script="/tmp/xingrun-class-feedback-period-frontend-red-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/class-feedback-generation.test.tsx
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: FAIL because `buildClassFeedbackPeriodPreview()` and `buildCreateClassFeedbackTaskRequest()` do not exist, and App source still contains raw `startDate` / `endDate` inputs.

- [ ] **Step 3: Implement the frontend helper module and App control-bar state**

In `frontend/src/classFeedbackGeneration.ts`, add explicit types and pure preview builders:

```ts
export type ClassFeedbackPeriodGranularity = 'daily' | 'weekly' | 'monthly' | 'stage' | 'custom';

export function buildClassFeedbackPeriodPreview(input:
  | { periodGranularity: 'daily'; anchorDate: string }
  | { periodGranularity: 'weekly'; year: number; week: number }
  | { periodGranularity: 'monthly'; year: number; month: number }
  | { periodGranularity: 'stage'; year: number; stageName: '春季' | '秋季' | '寒假' | '暑假' }
): { periodLabel: string; startDate: string; endDate: string } {
  if (input.periodGranularity === 'daily') {
    return { periodLabel: input.anchorDate, startDate: input.anchorDate, endDate: input.anchorDate };
  }
  if (input.periodGranularity === 'weekly') {
    const monday = new Date(Date.UTC(input.year, 0, 4));
    const firstWeekDay = (monday.getUTCDay() + 6) % 7;
    monday.setUTCDate(monday.getUTCDate() - firstWeekDay + (input.week - 1) * 7);
    const sunday = new Date(monday);
    sunday.setUTCDate(monday.getUTCDate() + 6);
    return {
      periodLabel: `${input.year}第${input.week}周`,
      startDate: monday.toISOString().slice(0, 10),
      endDate: sunday.toISOString().slice(0, 10),
    };
  }
  if (input.periodGranularity === 'monthly') {
    const firstDay = new Date(Date.UTC(input.year, input.month - 1, 1));
    const lastDay = new Date(Date.UTC(input.year, input.month, 0));
    return {
      periodLabel: `${input.year}${['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'][input.month - 1]}`,
      startDate: firstDay.toISOString().slice(0, 10),
      endDate: lastDay.toISOString().slice(0, 10),
    };
  }
  if (input.stageName === '春季') return { periodLabel: `${input.year}春季`, startDate: `${input.year}-02-01`, endDate: `${input.year}-06-30` };
  if (input.stageName === '暑假') return { periodLabel: `${input.year}暑假`, startDate: `${input.year}-07-01`, endDate: `${input.year}-08-31` };
  if (input.stageName === '秋季') return { periodLabel: `${input.year}秋季`, startDate: `${input.year}-09-01`, endDate: `${input.year + 1}-01-31` };
  return { periodLabel: `${input.year}寒假`, startDate: `${input.year}-01-01`, endDate: `${input.year}-02-${new Date(Date.UTC(input.year, 2, 0)).getUTCDate().toString().padStart(2, '0')}` };
}

export function buildCreateClassFeedbackTaskRequest(input:
  | { classId: number; periodGranularity: 'daily'; anchorDate: string }
  | { classId: number; periodGranularity: 'weekly'; year: number; week: number }
  | { classId: number; periodGranularity: 'monthly'; year: number; month: number }
  | { classId: number; periodGranularity: 'stage'; year: number; stageName: '春季' | '秋季' | '寒假' | '暑假' }
) {
  if (input.periodGranularity === 'daily') {
    return { class_id: input.classId, period_granularity: 'daily', anchor_date: input.anchorDate };
  }
  if (input.periodGranularity === 'weekly') {
    return { class_id: input.classId, period_granularity: 'weekly', year: input.year, week: input.week };
  }
  if (input.periodGranularity === 'monthly') {
    return { class_id: input.classId, period_granularity: 'monthly', year: input.year, month: input.month };
  }
  return { class_id: input.classId, period_granularity: 'stage', year: input.year, stage_name: input.stageName };
}
```

Update `createClassFeedbackTask()` to send the structured payload:

```ts
export const createClassFeedbackTask = (
  payload:
    | { classId: number; periodGranularity: 'daily'; anchorDate: string }
    | { classId: number; periodGranularity: 'weekly'; year: number; week: number }
    | { classId: number; periodGranularity: 'monthly'; year: number; month: number }
    | { classId: number; periodGranularity: 'stage'; year: number; stageName: '春季' | '秋季' | '寒假' | '暑假' },
) =>
  callApiFetch<ClassFeedbackTask>('/api/class-feedback/tasks', {
    method: 'POST',
    body: JSON.stringify(buildCreateClassFeedbackTaskRequest(payload)),
  });
```

In `frontend/src/App.tsx`, replace the date-range state with mode-specific state and preview:

```tsx
  const [classFeedbackPeriodGranularity, setClassFeedbackPeriodGranularity] = useState<'daily' | 'weekly' | 'monthly' | 'stage'>('weekly');
  const [classFeedbackAnchorDate, setClassFeedbackAnchorDate] = useState(() => getTodayIsoDate());
  const [classFeedbackPeriodYear, setClassFeedbackPeriodYear] = useState(() => Number(getTodayIsoDate().slice(0, 4)));
  const [classFeedbackPeriodWeek, setClassFeedbackPeriodWeek] = useState(1);
  const [classFeedbackPeriodMonth, setClassFeedbackPeriodMonth] = useState(() => Number(getTodayIsoDate().slice(5, 7)));
  const [classFeedbackStageName, setClassFeedbackStageName] = useState<'春季' | '秋季' | '寒假' | '暑假'>('春季');

  const classFeedbackPeriodPreview = useMemo(() => {
    if (classFeedbackPeriodGranularity === 'daily') {
      return buildClassFeedbackPeriodPreview({ periodGranularity: 'daily', anchorDate: classFeedbackAnchorDate });
    }
    if (classFeedbackPeriodGranularity === 'weekly') {
      return buildClassFeedbackPeriodPreview({ periodGranularity: 'weekly', year: classFeedbackPeriodYear, week: classFeedbackPeriodWeek });
    }
    if (classFeedbackPeriodGranularity === 'monthly') {
      return buildClassFeedbackPeriodPreview({ periodGranularity: 'monthly', year: classFeedbackPeriodYear, month: classFeedbackPeriodMonth });
    }
    return buildClassFeedbackPeriodPreview({ periodGranularity: 'stage', year: classFeedbackPeriodYear, stageName: classFeedbackStageName });
  }, [classFeedbackAnchorDate, classFeedbackPeriodGranularity, classFeedbackPeriodMonth, classFeedbackPeriodWeek, classFeedbackPeriodYear, classFeedbackStageName]);
```

Use `classFeedbackPeriodPreview.startDate` / `endDate` wherever the page currently reads `startDate` / `endDate` for lesson counting and summary text. In `handleCreateClassFeedbackTask()`, call the new payload shape instead of `{ startDate, endDate }`.

- [ ] **Step 4: Run the frontend tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
✔ buildClassFeedbackPeriodPreview derives normalized labels and ranges
✔ buildCreateClassFeedbackTaskRequest emits structured backend payloads
...
ℹ fail 0
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/classFeedbackGeneration.ts frontend/src/App.tsx frontend/src/class-feedback-generation.test.tsx
git commit -m "feat: add explicit class feedback period controls"
```

### Task 4: Surface Normalized Period Summaries And Final Proof

**Files:**
- Modify: `frontend/src/ClassFeedbackGenerationWorkspace.tsx`
- Modify: `frontend/src/class-feedback-generation.test.tsx`
- Modify: `handoff.md`

- [ ] **Step 1: Write the failing workspace-summary test**

Extend `frontend/src/class-feedback-generation.test.tsx` with this render assertion:

```tsx
test('ClassFeedbackGenerationWorkspace renders normalized period summary in the source list', () => {
  const markup = renderToStaticMarkup(
    <ClassFeedbackGenerationWorkspace
      classNameLabel="S01A1"
      teacherNameLabel="王老师"
      controlBar={<div>控制栏占位</div>}
      sourceSummaryItems={['反馈阶段：2026第15周', '覆盖范围：2026-04-06 至 2026-04-12']}
      labelGroups={defaultStageLabelGroups}
      classStatusTags={[]}
      students={[]}
      classSummaryText=""
      statusMessage="已创建反馈任务"
      draftStatusLabel="草稿已保存，可继续编辑。"
      stageNotes={{ classStatusNote: '', parentFeedbackNote: '', teachingFocusNote: '', nextStagePreviewNote: '' }}
      isGenerating={false}
      isSaving={false}
      isConfirming={false}
      onClassSummaryChange={() => undefined}
      onStageNoteChange={() => undefined}
      onClassStatusTagToggle={() => undefined}
      onHighlightToggle={() => undefined}
      onHighlightNoteChange={() => undefined}
      onStudentFinalTextChange={() => undefined}
      onStudentCheckedChange={() => undefined}
      onGenerate={() => undefined}
      onSaveDraft={() => undefined}
      onCopyClassSummary={() => undefined}
      onCopyAllStudents={() => undefined}
      onConfirm={() => undefined}
    />,
  );

  assert.match(markup, /反馈阶段：2026第15周/);
  assert.match(markup, /覆盖范围：2026-04-06 至 2026-04-12/);
});
```

- [ ] **Step 2: Run the focused frontend test to verify it fails**

Run:

```bash
tmp_script="/tmp/xingrun-class-feedback-period-summary-red-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/class-feedback-generation.test.tsx
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: FAIL because App source summary still prefers `时间范围：${startDate} 至 ${endDate}` and has not been updated to `反馈阶段：...`.

- [ ] **Step 3: Implement the summary and verification updates**

Update `frontend/src/App.tsx` source summary items to prefer normalized labels:

```tsx
  const sourceSummaryItems = [
    selectedClass ? `当前班级：${selectedClass.name}` : '当前班级：未选择',
    `反馈阶段：${classFeedbackPeriodPreview.periodLabel}`,
    `覆盖范围：${classFeedbackPeriodPreview.startDate} 至 ${classFeedbackPeriodPreview.endDate}`,
    `已命中 ${matchedLessonCount} 节课次记录`,
    `学生人数：${classFeedbackStudents.length} 名`,
    ...
  ];
```

Keep `ClassFeedbackGenerationWorkspace.tsx` generic; it only needs to keep rendering `sourceSummaryItems` in order. Then add the implementation result to `handoff.md` after tests are green.

- [ ] **Step 4: Run the full targeted proof and verify it passes**

Run:

```bash
tmp_script="/tmp/xingrun-class-feedback-period-proof-20260409.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
printf 'BACKEND\n'
/usr/bin/python3 -m unittest tests.test_class_feedback_store tests.test_class_feedback_api tests.test_organization_rooted_db_structure -v
printf '\nFRONTEND\n'
cd frontend
npx tsx --test src/class-feedback-generation.test.tsx
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected backend output ends with:

```text
Ran ... tests in ...s

OK
```

Expected frontend output ends with:

```text
ℹ pass ...
ℹ fail 0
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/ClassFeedbackGenerationWorkspace.tsx frontend/src/class-feedback-generation.test.tsx handoff.md
git commit -m "feat: show normalized class feedback period summaries"
```
