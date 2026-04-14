# Consultation Remarks List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show `follow_up_note` directly in the consultation list while keeping both desktop rows and mobile cards visually uniform without adding a new column or any expand-on-hover behavior.

**Architecture:** Keep the implementation inside the existing `ConsultationPage` in `frontend/src/App.tsx`. Reuse the existing consultation info blocks, append `备注：{followUpNote}` in place, and use fixed minimum-height budgets instead of adding a new layout abstraction. Lock the behavior with source-level assertions in the existing consultation test file so this stays a minimal front-end-only change.

**Tech Stack:** React, TypeScript, Tailwind utility classes, `tsx --test`

---

## File Map

- Modify: `frontend/src/App.tsx:4097-4229`
  - Add trimmed `follow_up_note` rendering to the mobile card info block and desktop `咨询科目 / 来源渠道` cell, plus fixed minimum-height classes so note-less and noted records stay the same size.
- Modify: `frontend/src/account-card.test.tsx:162-170`
  - Add a consultation-page source assertion that verifies the note stays inside the existing info blocks and no standalone `备注` table column appears.
- Modify: `handoff.md:8-68`
  - Record that the implementation plan exists and the next concrete step is to execute the small front-end-only change.

### Task 1: Lock The Intended Layout With A Failing Source Test

**Files:**
- Modify: `frontend/src/account-card.test.tsx:162-170`
- Modify: `frontend/src/App.tsx:4097-4229`

- [ ] **Step 1: Add a failing consultation-page source test**

```ts
test('consultation page source keeps follow-up notes inside the existing consultation info blocks', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const consultationPageBlock = source.match(/const ConsultationPage = \([\s\S]*?\n};/);

  assert.ok(consultationPageBlock);
  assert.match(consultationPageBlock[0], /const followUpNote = record\.follow_up_note\?\.trim\(\);/);
  assert.match(consultationPageBlock[0], /followUpNote && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">备注：\{followUpNote\}<\/p>/);
  assert.match(consultationPageBlock[0], /<div className="min-h-\[72px\] space-y-1 text-sm text-slate-500 dark:text-slate-400">/);
  assert.match(consultationPageBlock[0], /followUpNote && <p>备注：\{followUpNote\}<\/p>/);
  assert.doesNotMatch(consultationPageBlock[0], /font-semibold whitespace-nowrap">备注<\/th>/);
});
```

- [ ] **Step 2: Run the targeted front-end test through a temp script and confirm it fails**

Run:

```bash
tmp_script=$(mktemp -t xingrun-consultation-remarks-red)
mv "$tmp_script" "$tmp_script.sh"
tmp_script="$tmp_script.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/account-card.test.tsx
EOF
chmod +x "$tmp_script"
"$tmp_script"
rm -f "$tmp_script"
```

Expected: the new test fails because `ConsultationPage` does not yet trim or render `follow_up_note`, and there is no fixed-height note block in the current markup.

- [ ] **Step 3: Implement the smallest possible `App.tsx` change**

Use the two existing consultation list map blocks and add one local `followUpNote` variable to each layout instead of introducing a shared helper.

```tsx
{records.map((record) => {
  const busy = isBusy && selectedRecord?.id === record.id;
  const followUpNote = record.follow_up_note?.trim();
  return (
    <article key={record.id} className={`${workspaceSoftCardClass} space-y-4 p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">咨询日期</p>
          <p className="mt-2 font-mono text-sm text-slate-600 dark:text-slate-300">{record.date || '—'}</p>
        </div>
        <span className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-full px-3 py-1 text-[11px] font-semibold tracking-[0.08em] ${consultationStatusClass(record.follow_up_status || '')}`}>
          {record.follow_up_status || '—'}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">家长微信</p>
          <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">{record.parent_wechat_name || '—'}</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{getConsultationStudentMeta(record)}</p>
        </div>
        <div className="min-h-[96px]">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">咨询老师</p>
          <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">
            {getConsultationTeacherName(record, teacherDirectory)}
          </p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{record.consultation_subject || '未填写咨询科目'}</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{getConsultationSourceLabel(record)}</p>
          {followUpNote && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">备注：{followUpNote}</p>}
        </div>
      </div>
    </article>
  );
})}
```

```tsx
{records.map((record) => {
  const busy = isBusy && selectedRecord?.id === record.id;
  const followUpNote = record.follow_up_note?.trim();
  return (
    <tr key={record.id} className="group transition-colors hover:bg-sky-50/70 dark:hover:bg-white/5">
      <td className="px-6 py-4 font-mono text-sm text-slate-500 dark:text-slate-400">{record.date || '—'}</td>
      <td className="px-6 py-4">
        <div className="space-y-1">
          <p className="font-medium text-slate-900 dark:text-white">{record.parent_wechat_name || '—'}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">{getConsultationStudentMeta(record)}</p>
        </div>
      </td>
      <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">{record.grade || '—'}</td>
      <td className="px-6 py-4">
        <p className="text-sm text-slate-700 dark:text-slate-200">{getConsultationTeacherName(record, teacherDirectory)}</p>
      </td>
      <td className="px-6 py-4">
        <div className="min-h-[72px] space-y-1 text-sm text-slate-500 dark:text-slate-400">
          <p>{record.consultation_subject || '未填写咨询科目'}</p>
          <p>{getConsultationSourceLabel(record)}</p>
          {followUpNote && <p>备注：{followUpNote}</p>}
        </div>
      </td>
    </tr>
  );
})}
```

Implementation constraints:

- Do not add a new table header
- Do not add `overflow-x-auto`
- Do not add tooltip, modal, or expand/collapse state
- Keep the change inside the existing `ConsultationPage` block

- [ ] **Step 4: Re-run the targeted front-end tests through a temp script and confirm they pass**

Run:

```bash
tmp_script=$(mktemp -t xingrun-consultation-remarks-green)
mv "$tmp_script" "$tmp_script.sh"
tmp_script="$tmp_script.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/account-card.test.tsx src/workspace-navigation.test.ts
EOF
chmod +x "$tmp_script"
"$tmp_script"
rm -f "$tmp_script"
```

Expected: exit `0`; the new consultation-note assertion passes, and the existing adaptive-layout consultation test still passes without any horizontal-scroll regression.

### Task 2: Update Handoff, Re-Verify, And Commit The Small Front-End Change

**Files:**
- Modify: `handoff.md:8-68`
- Modify: `frontend/src/App.tsx:4097-4229`
- Modify: `frontend/src/account-card.test.tsx:162-170`

- [ ] **Step 1: Update `handoff.md` after the feature lands**

Replace the current consultation-note planning bullets with shipped-state bullets similar to:

```md
- 2026-04-14 已落地“咨询记录”页备注展示：备注不单独开列，直接并入现有“咨询科目 / 来源渠道”信息块；桌面端与移动端都按统一信息高度预算展示。

### 下一步
- 最值得继续做的是打开真实咨询记录页做一次人工 smoke check，确认有备注和无备注的记录在桌面端、移动端下都保持统一节奏。
```

Keep the existing long-term risk note about “备注通常不会太长”, because that remains true after implementation.

- [ ] **Step 2: Run one final temp-script proof against the exact touched tests**

Run:

```bash
tmp_script=$(mktemp -t xingrun-consultation-remarks-final)
mv "$tmp_script" "$tmp_script.sh"
tmp_script="$tmp_script.sh"
cat > "$tmp_script" <<'EOF'
#!/bin/zsh
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npx tsx --test src/account-card.test.tsx src/workspace-navigation.test.ts
EOF
chmod +x "$tmp_script"
"$tmp_script"
rm -f "$tmp_script"
```

Expected: exit `0` with both touched consultation-related test files green.

- [ ] **Step 3: Commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git add frontend/src/App.tsx frontend/src/account-card.test.tsx handoff.md
git commit -m "feat: show consultation remarks in list"
```
