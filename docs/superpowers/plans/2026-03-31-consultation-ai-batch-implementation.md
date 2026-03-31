# Consultation AI Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an AI-assisted batch entry flow to the existing `咨询记录` tab so staff can paste one text block, preview multiple draft creates or explicit-ID updates, and confirm writes through the existing consultation CRUD APIs.

**Architecture:** Keep the current consultation CSV storage model and single-record CRUD untouched. Add one parse-only Flask endpoint that cleans pasted text, calls a narrow AI parser, normalizes the returned drafts with the existing consultation domain rules, and returns preview data without writing records. In the React workspace, add one lightweight `AI 批量整理` modal inside the existing consultation page that calls the parse endpoint, shows draft items, and confirms them by looping through the existing `POST /api/consultations` and `PUT /api/consultations/:id` endpoints.

**Tech Stack:** Flask, Python `unittest`, existing OpenAI-compatible client in `ai_processor.py`, React 19, TypeScript, Vite, Node `test`

---

## File Structure

### Repo: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary`

- Modify: `lesson_manager.py`
  - Adds pasted-text cleanup and batch-draft normalization helpers that reuse existing consultation field rules.
- Modify: `ai_processor.py`
  - Adds a consultation-specific JSON prompt and one parse function that returns batch draft items without writing data.
- Modify: `app.py`
  - Adds `POST /api/consultations/ai-parse` and keeps the write path on the existing consultation CRUD endpoints.
- Modify: `tests/test_consultation_flow.py`
  - Covers explicit-ID update gating, WeChat merged-forward cleanup, and parse-endpoint response shape.
- Modify: `frontend/src/App.tsx`
  - Adds the `AI 批量整理` entry point, batch modal, parse preview, and confirm-import wiring inside the existing consultation page.
- Modify: `frontend/src/account-card.test.tsx`
  - Locks the new consultation batch entry and preview UI text into the repo’s existing source-level frontend test style.

This keeps the feature inside existing files and patterns, which matches the minimal-intrusion requirement.

### Task 1: Add The Backend Parse Contract Without Changing The Existing Consultation Write Model

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/tests/test_consultation_flow.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/lesson_manager.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/ai_processor.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/app.py`

- [ ] **Step 1: Write failing consultation-flow tests for explicit-ID updates and WeChat merged-forward cleanup**

```python
from unittest.mock import patch

    @patch("app.parse_consultation_batch_text")
    def test_ai_parse_endpoint_returns_create_and_explicit_id_update_drafts(self, mock_parse):
        self.write_teacher_aliases({"teacher-1": ["雷文浩"]})
        mock_parse.return_value = {
            "items": [
                {
                    "action": "create",
                    "target_id": None,
                    "reason": "未检测到显式记录ID，按新增处理",
                    "fields": {
                        "date": "2026-03-31",
                        "parent_wechat_name": "张妈妈",
                        "grade": "5年级",
                        "receiving_teacher": "雷文浩",
                        "consultation_subject": "数学",
                        "need_detail": "想补基础",
                        "source_channel": "朋友介绍",
                        "source_channel_note": "张裕空",
                        "follow_up_status": "待邀约",
                    },
                    "warnings": [],
                },
                {
                    "action": "update",
                    "target_id": 182,
                    "reason": "文本显式提到记录 ID 182",
                    "fields": {
                        "follow_up_status": "跟进中",
                        "follow_up_note": "已约周四试听",
                    },
                    "warnings": [],
                },
            ],
            "warnings": [],
        }

        response = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(self.owner_token),
            json={"raw_text": "新增：张妈妈，五年级数学。修改 ID 182：改成跟进中。"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([item["action"] for item in payload["items"]], ["create", "update"])
        self.assertEqual(payload["items"][0]["fields"]["grade"], "五年级")
        self.assertEqual(payload["items"][0]["fields"]["source_channel"], "转介绍")
        self.assertEqual(payload["items"][0]["fields"]["teacher_id"], "teacher-1")
        self.assertEqual(payload["items"][1]["target_id"], 182)

    @patch("app.parse_consultation_batch_text")
    def test_ai_parse_endpoint_cleans_wechat_forwarded_text_before_parsing(self, mock_parse):
        captured: dict[str, str] = {}

        def fake_parse(cleaned_text: str):
            captured["cleaned_text"] = cleaned_text
            return {
                "items": [
                    {
                        "action": "create",
                        "target_id": None,
                        "reason": "未检测到显式记录ID，按新增处理",
                        "fields": {
                            "parent_wechat_name": "李妈妈",
                            "consultation_subject": "英语",
                            "need_detail": "想先测评",
                        },
                        "warnings": [],
                    },
                    {
                        "action": "create",
                        "target_id": None,
                        "reason": "未检测到显式记录ID，按新增处理",
                        "fields": {
                            "parent_wechat_name": "王爸爸",
                            "consultation_subject": "数学",
                            "need_detail": "想补计算",
                        },
                        "warnings": [],
                    },
                ],
                "warnings": [],
            }

        mock_parse.side_effect = fake_parse

        response = self.client.post(
            "/api/consultations/ai-parse",
            headers=self.auth_headers(self.owner_token),
            json={
                "raw_text": "[聊天记录]\n张老师 2026-03-31 10:22\n李妈妈：孩子英语想先测评\n\n张老师 2026-03-31 10:25\n王爸爸：数学计算总错，想补基础"
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("2026-03-31 10:22", captured["cleaned_text"])
        self.assertIn("李妈妈", captured["cleaned_text"])
        self.assertIn("王爸爸", captured["cleaned_text"])
        self.assertEqual(len(response.get_json()["items"]), 2)
```

- [ ] **Step 2: Run the backend tests and confirm they fail because the parse endpoint and parser helpers do not exist yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_consultation_flow.ConsultationFlowTestCase.test_ai_parse_endpoint_returns_create_and_explicit_id_update_drafts tests.test_consultation_flow.ConsultationFlowTestCase.test_ai_parse_endpoint_cleans_wechat_forwarded_text_before_parsing`

Expected: FAIL with missing `POST /api/consultations/ai-parse` and missing `parse_consultation_batch_text` wiring.

- [ ] **Step 3: Add batch-input cleanup and normalized draft helpers in `lesson_manager.py` so the new endpoint reuses existing consultation domain rules**

```python
def clean_consultation_batch_input(raw_text: str) -> str:
    text = str(raw_text or "").replace("\r\n", "\n")
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"\[.*聊天记录.*\]", line):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}", line):
            continue
        line = re.sub(r"\b\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}\b", "", line).strip()
        line = re.sub(r"^[^：:\n]{1,20}\s+\d{1,2}:\d{2}$", "", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _normalize_consultation_batch_fields(fields: Optional[dict]) -> dict[str, str]:
    updates = _extract_consultation_updates(fields or {})
    normalized = {api_field: "" for api_field, csv_field in CONSULTATION_API_FIELD_MAP.items() if csv_field in CONSULTATION_EDITABLE_FIELDS}
    for api_field, csv_field in CONSULTATION_API_FIELD_MAP.items():
        if csv_field in updates:
            normalized[api_field] = updates[csv_field]

    normalized["grade"] = _normalize_consultation_grade(normalized.get("grade", ""))
    teacher_option = _get_consultation_teacher_directory()
    receiving_teacher = (normalized.get("receiving_teacher") or "").strip()
    if receiving_teacher:
        teacher_key = receiving_teacher.lower()
        teacher_display_name = teacher_option.get(teacher_key, "")
        if teacher_display_name:
            normalized["receiving_teacher"] = teacher_display_name
        alias_map = _load_consultation_teacher_aliases()
        for teacher_id, aliases in alias_map.items():
            if receiving_teacher in aliases or teacher_display_name and teacher_display_name in aliases:
                normalized["teacher_id"] = teacher_id
                break

    source_channel, source_note = _normalize_consultation_source_fields(
        normalized.get("source_channel", ""),
        source_note=normalized.get("source_channel_note", ""),
        parent_wechat_name=normalized.get("parent_wechat_name", ""),
        child_name=normalized.get("child_name", ""),
    )
    normalized["source_channel"] = source_channel
    normalized["source_channel_note"] = source_note
    return normalized


def normalize_consultation_batch_parse_result(payload: Optional[dict]) -> dict:
    data = payload or {}
    items = []
    for raw_item in data.get("items", []):
        action = "update" if raw_item.get("action") == "update" and raw_item.get("target_id") else "create"
        items.append({
            "action": action,
            "target_id": int(raw_item["target_id"]) if action == "update" else None,
            "reason": str(raw_item.get("reason", "")).strip(),
            "fields": _normalize_consultation_batch_fields(raw_item.get("fields")),
            "warnings": [str(item).strip() for item in raw_item.get("warnings", []) if str(item).strip()],
        })
    return {
        "items": items,
        "warnings": [str(item).strip() for item in data.get("warnings", []) if str(item).strip()],
    }
```

- [ ] **Step 4: Add the AI parser function in `ai_processor.py` and the parse-only Flask route in `app.py`**

```python
# ai_processor.py
CONSULTATION_BATCH_SYSTEM_PROMPT = """你是咨询记录整理助手。\n你只能输出 JSON。\n把输入拆成 items。\n只有文本中出现显式记录 ID（如 ID 182、记录182、#182）时，action 才能是 update。否则必须是 create。\nfields 只能包含 consultation 允许字段。\n"""


def parse_consultation_batch_text(raw_text: str) -> dict:
    client = _get_client()
    response = client.chat.completions.create(
        model=_get_chat_model(),
        messages=[
            {"role": "system", "content": CONSULTATION_BATCH_SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    payload = json.loads(response.choices[0].message.content)
    if not isinstance(payload.get("items"), list):
        raise RuntimeError("咨询记录批量解析返回了无效结果")
    return {
        "items": payload.get("items", []),
        "warnings": payload.get("warnings", []),
    }


# app.py
from ai_processor import parse_consultation_batch_text
from lesson_manager import clean_consultation_batch_input, normalize_consultation_batch_parse_result


@app.route("/api/consultations/ai-parse", methods=["POST"])
def api_consultation_ai_parse():
    _, error = _require_auth()
    if error:
        return error

    raw_text = str((request.json or {}).get("raw_text", "")).strip()
    if not raw_text:
        return jsonify({"error": "raw_text required"}), 400

    cleaned_text = clean_consultation_batch_input(raw_text)
    payload = parse_consultation_batch_text(cleaned_text)
    return jsonify(normalize_consultation_batch_parse_result(payload))
```

- [ ] **Step 5: Re-run the focused backend tests and then the full consultation-flow suite**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_consultation_flow.ConsultationFlowTestCase.test_ai_parse_endpoint_returns_create_and_explicit_id_update_drafts tests.test_consultation_flow.ConsultationFlowTestCase.test_ai_parse_endpoint_cleans_wechat_forwarded_text_before_parsing`

Expected: PASS with `Ran 2 tests` and `OK`.

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_consultation_flow`

Expected: PASS with the existing consultation CRUD tests still green.

- [ ] **Step 6: Commit the backend parse contract**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add tests/test_consultation_flow.py lesson_manager.py ai_processor.py app.py
git commit -m "feat: add consultation ai batch parse api"
```

### Task 2: Add The Consultation Batch Modal In The Existing Workspace And Keep Frontend Verification Minimal

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/account-card.test.tsx`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend/src/App.tsx`

- [ ] **Step 1: Write failing frontend source tests that lock the new batch entry and preview copy into the consultation workspace**

```tsx
test('consultation source exposes ai batch entry and parse preview copy', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /AI 批量整理/);
  assert.match(source, /智能解析/);
  assert.match(source, /确认导入/);
  assert.match(source, /仅当文本中出现记录 ID 时才会按更新处理/);
});

test('consultation source keeps batch import on top of existing consultation crud endpoints', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.match(source, /apiFetch<\{ items: ConsultationBatchDraft\[]; warnings: string\[] \}>\('\/api\/consultations\/ai-parse'/);
  assert.match(source, /await apiFetch\('\/api\/consultations', \{/);
  assert.match(source, /await apiFetch\(`\/api\/consultations\/\$\{draft.target_id\}`, \{/);
});
```

- [ ] **Step 2: Run the frontend test file and confirm it fails because the batch entry and parse flow are not wired yet**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/account-card.test.tsx`

Expected: FAIL with missing `AI 批量整理` UI text and missing `api-parse` request pattern.

- [ ] **Step 3: Add batch draft types and a lightweight batch modal component in `App.tsx`**

```tsx
interface ConsultationBatchDraft {
  action: 'create' | 'update';
  target_id: number | null;
  reason: string;
  fields: Partial<ConsultationFormValues>;
  warnings: string[];
}

const ConsultationBatchModal = ({
  open,
  submitting,
  parseError,
  onClose,
  onParse,
  onConfirm,
}: {
  open: boolean;
  submitting: boolean;
  parseError: string;
  onClose: () => void;
  onParse: (rawText: string) => Promise<void>;
  onConfirm: () => Promise<void>;
}) => {
  const [rawText, setRawText] = useState('');
  const [drafts, setDrafts] = useState<ConsultationBatchDraft[]>([]);

  if (!open) {
    return null;
  }

  return (
    <motion.div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-3 py-3 sm:items-center sm:px-4 sm:py-6">
      <div className="absolute inset-0 bg-black/45 backdrop-blur-[6px]" />
      <motion.div className="relative z-10 my-auto flex w-full max-w-5xl flex-col overflow-hidden rounded-[1.5rem] border border-sky-100 bg-white shadow-[0_30px_90px_rgba(15,23,42,0.18)] dark:border-white/10 dark:bg-slate-900">
        <div className="border-b border-sky-100/80 px-4 py-4 dark:border-white/10">
          <h3 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">AI 批量整理</h3>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">支持自然语言和微信合并转发文本。仅当文本中出现记录 ID 时才会按更新处理。</p>
        </div>
        <div className="space-y-4 px-4 py-4 sm:px-6 sm:py-5">
          <textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            rows={8}
            className={`${workspaceFieldClass} resize-none`}
            placeholder="例如：新增：张妈妈，五年级数学，雷文浩接待。修改 ID 182：改成跟进中。"
          />
          {parseError ? <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">{parseError}</div> : null}
          <div className="space-y-3">
            {drafts.map((draft, index) => (
              <div key={`${draft.action}-${draft.target_id ?? 'new'}-${index}`} className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-slate-900 dark:text-white">{draft.action === 'update' ? `更新 #${draft.target_id}` : '新增'}</span>
                  <button type="button" className={workspaceSecondaryButtonClass}>移除</button>
                </div>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{draft.reason}</p>
                <p className="mt-2 text-sm text-slate-700 dark:text-slate-200">{draft.fields.parent_wechat_name || '未识别家长'} / {draft.fields.consultation_subject || '未识别科目'} / {draft.fields.follow_up_status || '待邀约'}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-3 border-t border-sky-100/80 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 dark:border-white/10">
          <div className="text-sm text-slate-500 dark:text-slate-400">待导入 {drafts.length} 条</div>
          <div className="grid gap-3 sm:flex sm:flex-wrap sm:justify-end">
            <button type="button" onClick={() => onParse(rawText)} className={workspaceSecondaryButtonClass}>智能解析</button>
            <button type="button" onClick={onConfirm} className={workspacePrimaryButtonClass} disabled={submitting || drafts.length === 0}>确认导入</button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
};
```

- [ ] **Step 4: Wire the consultation page to open the batch modal, call the parse endpoint, and confirm drafts through the existing write endpoints**

```tsx
const ConsultationPage = ({ currentUser }: { currentUser: CurrentUser }) => {
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [batchDrafts, setBatchDrafts] = useState<ConsultationBatchDraft[]>([]);
  const [batchWarnings, setBatchWarnings] = useState<string[]>([]);
  const [batchError, setBatchError] = useState('');

  const handleBatchParse = async (rawText: string) => {
    setBatchError('');
    const payload = await apiFetch<{ items: ConsultationBatchDraft[]; warnings: string[] }>('/api/consultations/ai-parse', {
      method: 'POST',
      body: JSON.stringify({ raw_text: rawText }),
    });
    setBatchDrafts(payload.items);
    setBatchWarnings(payload.warnings);
  };

  const handleBatchConfirm = async () => {
    setSubmitting(true);
    setBatchError('');
    try {
      for (const draft of batchDrafts) {
        const payload = {
          ...consultationFormDefaults,
          ...draft.fields,
        };
        if (draft.action === 'update' && draft.target_id) {
          await apiFetch(`/api/consultations/${draft.target_id}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
          });
        } else {
          await apiFetch('/api/consultations', {
            method: 'POST',
            body: JSON.stringify(payload),
          });
        }
      }
      setBatchModalOpen(false);
      setBatchDrafts([]);
      setBatchWarnings([]);
      await load(search);
    } catch (err) {
      setBatchError(err instanceof Error ? err.message : 'AI 批量导入失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <div className="flex flex-wrap items-center gap-3 self-start lg:self-auto">
        <button type="button" onClick={() => setBatchModalOpen(true)} className={`${workspaceSecondaryButtonClass} w-full sm:w-auto sm:min-w-[126px]`}>
          <Cpu size={18} />
          AI 批量整理
        </button>
        <button type="button" onClick={openCreateModal} className={`${workspacePrimaryButtonClass} w-full sm:w-auto sm:min-w-[126px]`}>
          <PlusCircle size={18} />
          新增记录
        </button>
      </div>

      <AnimatePresence>
        {batchModalOpen && (
          <ConsultationBatchModal
            open={batchModalOpen}
            submitting={submitting}
            parseError={batchError}
            onClose={() => setBatchModalOpen(false)}
            onParse={handleBatchParse}
            onConfirm={handleBatchConfirm}
          />
        )}
      </AnimatePresence>
    </div>
  );
};
```

- [ ] **Step 5: Re-run the frontend source tests and confirm the new consultation batch flow is covered without breaking existing assertions**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/account-card.test.tsx`

Expected: PASS with the new consultation batch assertions and the existing consultation modal tests still green.

- [ ] **Step 6: Commit the frontend batch workflow**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/account-card.test.tsx
git commit -m "feat: add consultation ai batch modal"
```

### Task 3: Run Final Feature Verification And Leave A Clear Handoff

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Review/handoff.md`

- [ ] **Step 1: Run the exact backend and frontend verification commands for the new feature**

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python -m unittest tests.test_consultation_flow`

Expected: PASS with all consultation-flow tests green.

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend && npx tsx --test src/account-card.test.tsx`

Expected: PASS with the consultation batch entry assertions present.

- [ ] **Step 2: Run one temporary proof script that shows the new parse endpoint can return mixed draft actions without writing records**

```python
from unittest.mock import patch

from app import app

client = app.test_client()
login = client.post('/api/login', json={'username': 'Kayn', 'password': 'xingrun2026'})
token = login.get_json()['token']

with patch('app.parse_consultation_batch_text') as mock_parse:
    mock_parse.return_value = {
        'items': [
            {
                'action': 'create',
                'target_id': None,
                'reason': '未检测到显式记录ID，按新增处理',
                'fields': {'parent_wechat_name': '张妈妈', 'consultation_subject': '数学'},
                'warnings': [],
            },
            {
                'action': 'update',
                'target_id': 182,
                'reason': '文本显式提到记录 ID 182',
                'fields': {'follow_up_status': '跟进中'},
                'warnings': [],
            },
        ],
        'warnings': [],
    }
    response = client.post(
        '/api/consultations/ai-parse',
        headers={'X-Auth-Token': token},
        json={'raw_text': '新增：张妈妈。修改 ID 182：改成跟进中。'},
    )
    print(response.status_code)
    print(response.get_json())
```

Run: `cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary && /Users/ark.mini/Desktop/Xingrun-Review/.venv/bin/python /tmp/consultation_ai_batch_proof.py`

Expected: `200` plus a JSON payload with one `create` item and one `update` item, and no consultation CSV write happening during parse.

- [ ] **Step 3: Update the workspace handoff with what shipped, what was verified, and what was intentionally deferred**

```md
补充记录（2026-03-31，咨询记录 AI 批量整理已完成最小版实现）
- 已新增 `AI 批量整理` 入口，支持自然语言与微信合并转发文本粘贴解析。
- 第一版保持 draft-first：AI 只生成草稿，不直接写库。
- 修改旧记录仅支持显式记录 ID。
- 已验证：
  - `tests.test_consultation_flow`
  - `frontend/src/account-card.test.tsx`
  - 临时 parse proof 脚本
- 暂未实现：OCR、原生文件导入、模糊匹配历史记录更新。
```

- [ ] **Step 4: Commit the final handoff note after verification**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git status --short
git commit -am "docs: update consultation ai batch handoff"
```

## Self-Review

- Spec coverage: covered the new UI entry, parse-only backend route, explicit-ID update rule, WeChat merged-forward cleanup, preview-before-save behavior, and minimal verification.
- Placeholder scan: no `TBD`, `TODO`, or deferred implementation markers are left inside executable steps.
- Type consistency: the plan uses one backend endpoint name, one draft item shape, one explicit-ID update rule, and the existing consultation CRUD endpoints throughout.