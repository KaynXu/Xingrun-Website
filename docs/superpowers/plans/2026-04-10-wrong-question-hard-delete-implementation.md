# Wrong Question Hard Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real `删除本题` flow for local WeChat wrong questions in the website workspace, delete stale student-library PDFs before rebuilding, and move the UI to the next question after a successful delete.

**Architecture:** The backend remains the source of truth. `lesson_manager.py` gets small helpers for deleting one local WeChat wrong-question row and resetting or repopulating student PDF path snapshots, while `app.py` owns the authenticated delete endpoint and student-library PDF cleanup/rebuild flow. `SmartWrongQuestionsPage.tsx` adds one local-only delete action and updates notebook selection state in memory instead of reloading the whole page.

**Tech Stack:** Flask, SQLite, Python `unittest`, React, Vite, `tsx --test`

---

## File Map

- Modify: `lesson_manager.py`
  - Add minimal helpers to delete one local WeChat wrong-question record and batch-update PDF path snapshots for a student.
- Modify: `app.py`
  - Add `DELETE /api/wrong-questions/<record_id>` for local WeChat records and rebuild or clear the student PDF after deletion.
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`
  - Show the delete button for local WeChat records, call the delete endpoint, and move selection to the next question.
- Modify: `tests/test_wechat_parent_reason_flow.py`
  - Cover backend deletion permissions, data deletion, PDF cleanup, and last-record behavior.
- Modify: `frontend/src/smart-wrong-questions.test.ts`
  - Cover delete button visibility, API call shape, next-record selection, and empty-detail behavior.
- Modify: `handoff.md`
  - Record that hard delete + PDF cleanup shipped and note any remaining risk.

### Task 1: Add Backend Delete Coverage First

**Files:**
- Modify: `tests/test_wechat_parent_reason_flow.py`
- Modify: `app.py`
- Modify: `lesson_manager.py`

- [ ] **Step 1: Write the failing backend tests**

```python
def test_visible_user_can_delete_local_wrong_question_and_rebuild_pdf(self):
    pdf_dir = self.base / "pdfs" / "wrong_question_libraries"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"student-{self.student['id']}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nold pdf\n")

    second = lesson_manager.create_wechat_wrong_question_submission(
        binding_id=self.binding["id"],
        image_url="https://files.example.com/wrong-question-2.png",
        child_raw_reason_text="第二题",
        primary_error_type="计算问题",
        secondary_error_summary="第二题备注",
        recognition_status="recognized",
        question_text="第二题题干",
        question_text_source="ai",
        student_library_pdf_path=str(pdf_path),
    )

    with lesson_manager.get_conn() as conn:
        conn.execute(
            "UPDATE wrong_question_submissions SET recognition_status='recognized', question_text='第一题题干', student_library_pdf_path=? WHERE id=?",
            (str(pdf_path), self.record_id),
        )

    with patch("app._rebuild_student_wrong_question_library", return_value=str(pdf_path)) as rebuild:
        response = self.client.delete(
            f"/api/wrong-questions/{self.record_id}",
            headers=self.auth_headers(self.owner_payload["token"]),
        )

    self.assertEqual(response.status_code, 200)
    payload = response.get_json()
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["deleted_record_id"], self.record_id)
    self.assertEqual(lesson_manager.get_wechat_wrong_question_submission(self.record_id), None)
    self.assertEqual(rebuild.call_count, 1)


def test_delete_last_local_wrong_question_removes_pdf_without_rebuild(self):
    pdf_dir = self.base / "pdfs" / "wrong_question_libraries"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"student-{self.student['id']}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nold pdf\n")

    with lesson_manager.get_conn() as conn:
        conn.execute(
            "UPDATE wrong_question_submissions SET recognition_status='recognized', question_text='最后一题', student_library_pdf_path=? WHERE id=?",
            (str(pdf_path), self.record_id),
        )

    with patch("app._rebuild_student_wrong_question_library") as rebuild:
        response = self.client.delete(
            f"/api/wrong-questions/{self.record_id}",
            headers=self.auth_headers(self.owner_payload["token"]),
        )

    self.assertEqual(response.status_code, 200)
    self.assertFalse(pdf_path.exists())
    self.assertEqual(rebuild.call_count, 0)


def test_visible_member_can_delete_local_wrong_question(self):
    with lesson_manager.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name, role, status, organization_id)
            VALUES (?, ?, ?, 'member', 'active', ?)
            """,
            ("member_delete", "hash", "Member Delete", self.owner_payload["user"]["organization_id"]),
        )
        member_id = cur.lastrowid
    member_token = lesson_manager.create_auth_session(member_id)
    lesson_manager.set_user_class_ids(member_id, [self.class_id])

    response = self.client.delete(
        f"/api/wrong-questions/{self.record_id}",
        headers=self.auth_headers(member_token),
    )

    self.assertEqual(response.status_code, 200)
```

- [ ] **Step 2: Run the backend tests to verify they fail**

Run:

```bash
tmp_script="/tmp/xingrun-wq-delete-backend-red.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
/usr/bin/python3 -m unittest tests.test_wechat_parent_reason_flow -v
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: `AttributeError` or `405` because the delete route and storage helpers do not exist yet.

- [ ] **Step 3: Add the minimal data-layer helpers**

```python
def delete_wechat_wrong_question_submission(record_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = _fetch_wechat_wrong_question_submission_row_by_id(conn, record_id)
        if not row:
            return None
        serialized = _serialize_wechat_wrong_question_submission_row(row)
        conn.execute("DELETE FROM wrong_question_submissions WHERE id=?", (record_id,))
    return serialized


def set_student_wrong_question_library_pdf_path(student_id: int, pdf_path: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE wrong_question_submissions
            SET student_library_pdf_path=?,
                updated_at=datetime('now','localtime')
            WHERE student_id=?
            """,
            ((pdf_path or "").strip(), student_id),
        )
```

- [ ] **Step 4: Add the delete endpoint and PDF cleanup flow**

```python
@app.route("/api/wrong-questions/<record_id>", methods=["DELETE"])
def api_wrong_question_delete(record_id):
    user, error = _require_auth()
    if error:
        return error

    local_record = get_wechat_wrong_question_submission(record_id)
    if not local_record or not _can_access_wrong_question_record(user, local_record):
        return jsonify({"error": "not found"}), 404

    student_id = int(local_record["student_id"])
    pdf_path = _student_wrong_question_library_path(student_id)
    deleted_record = delete_wechat_wrong_question_submission(record_id)
    if not deleted_record:
        return jsonify({"error": "not found"}), 404

    pdf_path.unlink(missing_ok=True)
    remaining_records = list_student_wrong_question_library_records(student_id)
    next_pdf_path = ""
    if remaining_records:
        next_pdf_path = _rebuild_student_wrong_question_library(student_id)
        set_student_wrong_question_library_pdf_path(student_id, next_pdf_path)
    else:
        set_student_wrong_question_library_pdf_path(student_id, "")

    return jsonify({
        "ok": True,
        "deleted_record_id": record_id,
        "student_id": student_id,
        "next_student_library_pdf_path": next_pdf_path,
    })
```

- [ ] **Step 5: Run the backend tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
Ran ... tests in ...

OK
```

- [ ] **Step 6: Commit**

```bash
git add app.py lesson_manager.py tests/test_wechat_parent_reason_flow.py
git commit -m "feat: add local wrong question hard delete api"
```

### Task 2: Add Frontend Delete Coverage First

**Files:**
- Modify: `frontend/src/smart-wrong-questions.test.ts`
- Modify: `frontend/src/SmartWrongQuestionsPage.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```ts
test('SmartWrongQuestionsPage shows a delete button for local wechat records only', () => {
  const pageSource = readFileSync(resolve(currentDir, 'SmartWrongQuestionsPage.tsx'), 'utf8');

  assert.match(pageSource, /删除本题/);
  assert.match(pageSource, /selectedRecord\.source === 'wechat_mp'/);
  assert.match(pageSource, /method: 'DELETE'/);
});


test('SmartWrongQuestionsPage deletes a wechat record and jumps to the next notebook record', async () => {
  const domEnvironment = setupDomEnvironment();
  const originalFetch = globalThis.fetch;
  const fetchCalls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  let root: Root | null = null;

  try {
    localStorage.setItem('xr_token', 'token-123');
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      fetchCalls.push({ input, init });

      if (input === '/api/classes') {
        return createJsonResponse([{ id: 42, name: '六年级 1 班', subject: '数学' }]);
      }
      if (input === '/api/admin/users') {
        return createJsonResponse([]);
      }
      if (input === '/api/wrong-questions' || (typeof input === 'string' && input.startsWith('/api/wrong-questions?'))) {
        return createJsonResponse({
          items: [
            { id: 'wechat-a', source: 'wechat_mp', student_name: 'Alice', class_display_name: '六年级 1 班', class_id: 42, teacher_display_name: 'Kayn', created_at: '2026-03-29T08:00:00Z', recognition_status: 'recognized', question_text: '第一题', student_library_pdf_path: '/api/wechat/student-libraries/1', analysis: {} },
            { id: 'wechat-b', source: 'wechat_mp', student_name: 'Alice', class_display_name: '六年级 1 班', class_id: 42, teacher_display_name: 'Kayn', created_at: '2026-03-29T09:00:00Z', recognition_status: 'recognized', question_text: '第二题', student_library_pdf_path: '/api/wechat/student-libraries/1', analysis: {} },
          ],
          summary: { total_count: 2, repeated_mistake_count: 0, high_priority_count: 0, pending_review_count: 2 },
        });
      }
      if (input === '/api/wrong-questions/wechat-a' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({ id: 'wechat-a', source: 'wechat_mp', student_name: 'Alice', class_display_name: '六年级 1 班', class_id: 42, teacher_display_name: 'Kayn', created_at: '2026-03-29T08:00:00Z', recognition_status: 'recognized', question_text: '第一题', student_library_pdf_path: '/api/wechat/student-libraries/1', archive_status: 'active', analysis: {} });
      }
      if (input === '/api/wrong-questions/wechat-b' && (!init?.method || init.method === 'GET')) {
        return createJsonResponse({ id: 'wechat-b', source: 'wechat_mp', student_name: 'Alice', class_display_name: '六年级 1 班', class_id: 42, teacher_display_name: 'Kayn', created_at: '2026-03-29T09:00:00Z', recognition_status: 'recognized', question_text: '第二题', student_library_pdf_path: '/api/wechat/student-libraries/1', archive_status: 'active', analysis: {} });
      }
      if (input === '/api/wrong-questions/wechat-a' && init?.method === 'DELETE') {
        return createJsonResponse({ ok: true, deleted_record_id: 'wechat-a', student_id: 1, next_student_library_pdf_path: '/api/wechat/student-libraries/1' });
      }

      throw new Error(`Unexpected fetch: ${String(input)}`);
    }) as typeof fetch;

    const originalConfirm = window.confirm;
    window.confirm = () => true;

    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(React.createElement(SmartWrongQuestionsPage, {
        currentUser: { display_name: '管理员', organization_name: '星润Starain', role: 'owner' },
      }));
    });

    await selectNotebookClass(domEnvironment.container, '42');
    await openNotebookStudent(domEnvironment.container, 'Alice');

    const deleteButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('删除本题'));
    assert.ok(deleteButton instanceof HTMLButtonElement);

    await act(async () => {
      deleteButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 0));
    });

    await waitForAssertion(() => {
      const deleteCall = fetchCalls.findLast((call) => call.input === '/api/wrong-questions/wechat-a' && call.init?.method === 'DELETE');
      assert.ok(deleteCall);
      assert.match(domEnvironment.container.textContent || '', /第二题/);
    });

    window.confirm = originalConfirm;
  } finally {
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    globalThis.fetch = originalFetch;
    domEnvironment.cleanup();
  }
});
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run:

```bash
tmp_script="/tmp/xingrun-wq-delete-frontend-red.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/smart-wrong-questions.test.ts
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected: assertion failure because there is no delete button and no delete fetch call yet.

- [ ] **Step 3: Add the minimal delete UI and state transition**

```tsx
const handleDeleteRecord = async () => {
  if (!selectedRecord || selectedRecord.source !== 'wechat_mp') {
    return;
  }
  if (!window.confirm('确定删除这道错题吗？删除后会同步更新该学生错题库 PDF。')) {
    return;
  }

  setSaveError('');
  await apiFetch(`/api/wrong-questions/${encodeURIComponent(selectedRecord.id)}`, { method: 'DELETE' });

  const nextRecords = memberNotebookRecords.filter((item) => item.id !== selectedRecord.id);
  setRecords((current) => current.filter((item) => item.id !== selectedRecord.id));
  setReviewDraftByRecordId((current) => {
    const next = { ...current };
    delete next[selectedRecord.id];
    return next;
  });
  setReviewDraftDirtyByRecordId((current) => {
    const next = { ...current };
    delete next[selectedRecord.id];
    return next;
  });
  setSelectedId(nextRecords[0]?.id ?? null);
};
```

- [ ] **Step 4: Run the frontend tests to verify they pass**

Run the same temp script from Step 2.

Expected:

```text
... smart-wrong-questions.test.ts
# pass ...
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: add smart wrong question hard delete ui"
```

### Task 3: Final Verification, Handoff, And External Prompt

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Update `handoff.md` with shipped behavior**

```md
- 本轮已落地：网站端微信错题详情支持 `删除本题`；删除后会先删旧学生错题库 PDF，再按剩余有效题决定重建或清空，前端会自动跳到同学生下一题。
```

- [ ] **Step 2: Run focused backend and frontend verification**

Run:

```bash
tmp_script="/tmp/xingrun-wq-delete-green.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website
/usr/bin/python3 -m unittest tests.test_wechat_parent_reason_flow -v
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/smart-wrong-questions.test.ts
EOF
chmod +x "$tmp_script"
"$tmp_script"
```

Expected:

```text
OK
...
# pass ...
```

- [ ] **Step 3: Commit the verified result**

```bash
git add handoff.md
git commit -m "docs: record wrong question hard delete rollout"
```

- [ ] **Step 4: Prepare the external mini-program AI prompt for the final handoff**

```text
请在微信错题详情或错题库页新增一个“删除本题”按钮，仅对本地微信错题记录显示。点击后先二次确认，确认文案必须明确“删除后会同步更新该学生错题库 PDF”。确认后调用删除接口，接口建议使用 DELETE /api/wrong-questions/:id。删除成功后：
1. 从当前学生错题列表移除这道题
2. 如果还有下一题，自动跳到下一题
3. 如果已经没有题，回到空列表状态
4. 不要保留已删除题的旧详情缓存
5. 删除失败时保留当前页并展示错误提示
```

## Self-Review

- Spec coverage: the backend task covers hard delete, visibility-based permission, and PDF cleanup; the frontend task covers the local-only button and next-question behavior; the final task covers handoff and the external mini-program prompt.
- Placeholder scan: no `TODO`, `TBD`, or “implement later” markers remain.
- Type consistency: endpoint path, record ID shape, and `wechat_mp` gating match the approved spec.
