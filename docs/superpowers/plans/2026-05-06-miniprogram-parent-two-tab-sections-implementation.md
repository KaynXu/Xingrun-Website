# Miniprogram Parent Two Tab Sections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the parent mini program into two bottom Tab sections: `我的` for child binding/current-child selection, and `拍照上传` for uploading wrong questions for the selected child.

**Architecture:** Keep the existing page files and APIs. Add tabBar configuration in `app.json`, add small current-binding helpers to `utils/parentApi.js`, make `parent-home` set/show the current upload child, and make `parent-upload` choose a binding when opened as a tab without `bindingId`.

**Tech Stack:** WeChat Mini Program WXML/WXSS/JS, Node built-in test runner, existing static guardrail shell scripts.

---

## File Structure

- Modify `miniprogram/miniprogram/app.json`: add the two-item `tabBar`.
- Modify `miniprogram/miniprogram/utils/parentApi.js`: add `CURRENT_PARENT_BINDING_KEY`, `getCurrentParentBindingId()`, `setCurrentParentBindingId()`, and update `resolveParentEntryPath()` to enter the `我的` tab when a parent has cached bindings.
- Modify `miniprogram/miniprogram/pages/parent-home/index.js`: load and set the current upload child.
- Modify `miniprogram/miniprogram/pages/parent-home/index.wxml`: change copy to `我的孩子`, remove child-card upload buttons, add current-child action.
- Modify `miniprogram/miniprogram/pages/parent-home/index.wxss`: style the current-child action without changing shared button primitives.
- Modify `miniprogram/miniprogram/pages/parent-upload/index.js`: support tab entry without `bindingId`, binding selection, and switchTab navigation to `我的`.
- Modify `miniprogram/miniprogram/pages/parent-upload/index.wxml`: show no-child and choose-child states before the existing upload flow.
- Modify `miniprogram/miniprogram/pages/parent-upload/index.wxss`: style the upload child selector.
- Modify `miniprogram/miniprogram/parent-only-scope.test.js`: static contracts for tabBar and page copy.
- Modify `miniprogram/miniprogram/utils/parentApi.test.js`: helper behavior.
- Modify `miniprogram/miniprogram/pages/parent-home/index.test.js`: page behavior for setting current child.
- Modify `miniprogram/miniprogram/pages/parent-upload/index.test.js`: no-`bindingId` tab entry behavior.
- Modify `scripts/ralph/miniprogram_visual_polish_proof.sh` only if its current home-page expectations still require the removed upload button.
- Modify `handoff.md` and `miniprogram/handoff.md` after implementation.

---

### Task 1: Current Binding Helpers

**Files:**
- Modify: `miniprogram/miniprogram/utils/parentApi.js`
- Test: `miniprogram/miniprogram/utils/parentApi.test.js`

- [ ] **Step 1: Write the failing tests**

Add tests for storing the selected binding and for entry path behavior:

```js
test('current parent binding helper stores and clears the selected upload child', () => {
  const storage = {};
  const wxApi = {
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value;
    },
  };

  assert.equal(getCurrentParentBindingId(wxApi), 0);
  setCurrentParentBindingId(wxApi, 21);
  assert.equal(getCurrentParentBindingId(wxApi), 21);
  setCurrentParentBindingId(wxApi, 0);
  assert.equal(getCurrentParentBindingId(wxApi), 0);
});

test('resolveParentEntryPath enters the my tab when cached bindings exist', () => {
  const storage = {};
  const wxApi = {
    getStorageSync: (key) => storage[key] || '',
    setStorageSync: (key, value) => {
      storage[key] = value;
    },
  };

  assert.equal(resolveParentEntryPath(wxApi), '/pages/parent-bind/index');
  upsertParentBinding(wxApi, { id: 21, studentId: 7, studentName: '小星' });
  assert.equal(resolveParentEntryPath(wxApi), '/pages/parent-home/index');
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
node --test miniprogram/miniprogram/utils/parentApi.test.js
```

Expected: fail because `getCurrentParentBindingId` and `setCurrentParentBindingId` are not exported.

- [ ] **Step 3: Implement minimal helpers**

In `parentApi.js`, add:

```js
const CURRENT_PARENT_BINDING_KEY = 'xr_current_parent_binding_id';

function getCurrentParentBindingId(wxApi) {
  return Number(safeGetStorage(wxApi, CURRENT_PARENT_BINDING_KEY, 0) || 0) || 0;
}

function setCurrentParentBindingId(wxApi, bindingId) {
  safeSetStorage(wxApi, CURRENT_PARENT_BINDING_KEY, Number(bindingId) || 0);
}
```

Export both helpers and `CURRENT_PARENT_BINDING_KEY`.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
node --test miniprogram/miniprogram/utils/parentApi.test.js
```

Expected: all tests pass.

---

### Task 2: Tab Bar and My Page

**Files:**
- Modify: `miniprogram/miniprogram/app.json`
- Modify: `miniprogram/miniprogram/pages/parent-home/index.js`
- Modify: `miniprogram/miniprogram/pages/parent-home/index.wxml`
- Modify: `miniprogram/miniprogram/pages/parent-home/index.wxss`
- Test: `miniprogram/miniprogram/parent-only-scope.test.js`
- Test: `miniprogram/miniprogram/pages/parent-home/index.test.js`

- [ ] **Step 1: Write failing static tests**

In `parent-only-scope.test.js`, update or add contracts:

```js
test('parent mini program exposes my and photo upload as the only bottom tabs', () => {
  const appConfigPath = path.join(MINIPROGRAM_DIR, 'app.json');
  const appConfig = JSON.parse(fs.readFileSync(appConfigPath, 'utf8'));

  assert.deepEqual(appConfig.tabBar.list.map((item) => ({
    pagePath: item.pagePath,
    text: item.text,
  })), [
    { pagePath: 'pages/parent-home/index', text: '我的' },
    { pagePath: 'pages/parent-upload/index', text: '拍照上传' },
  ]);
});

test('parent home is the my section and no longer exposes upload actions inside child cards', () => {
  const homeTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxml'), 'utf8');

  assert.equal(homeTemplate.includes('我的孩子'), true);
  assert.equal(homeTemplate.includes('设置当前上传孩子'), true);
  assert.equal(homeTemplate.includes('上传错题'), false);
  assert.equal(homeTemplate.includes('查看错题本'), true);
});
```

- [ ] **Step 2: Write failing page behavior tests**

Create `miniprogram/miniprogram/pages/parent-home/index.test.js` with a minimal page harness. Test that `onShow()` auto-selects a current child when there is one binding and that `setCurrentBinding()` stores the selected id.

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
node --test miniprogram/miniprogram/parent-only-scope.test.js miniprogram/miniprogram/pages/parent-home/index.test.js
```

Expected: fail because `tabBar` and current-child UI/actions are missing.

- [ ] **Step 4: Implement tabBar and home UI**

Add to `app.json`:

```json
"tabBar": {
  "color": "#60738f",
  "selectedColor": "#2375d8",
  "backgroundColor": "#ffffff",
  "borderStyle": "white",
  "list": [
    { "pagePath": "pages/parent-home/index", "text": "我的" },
    { "pagePath": "pages/parent-upload/index", "text": "拍照上传" }
  ]
}
```

Update `parent-home` to:

- Set hero title to `我的孩子`.
- Show `当前上传孩子` when `item.id === currentBindingId`.
- Replace the upload button with `设置当前上传孩子`.
- Keep `查看错题本`.
- Use `setCurrentParentBindingId()` in the new event handler.

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
node --test miniprogram/miniprogram/parent-only-scope.test.js miniprogram/miniprogram/pages/parent-home/index.test.js
```

Expected: all tests pass.

---

### Task 3: Upload Tab Binding Selection

**Files:**
- Modify: `miniprogram/miniprogram/pages/parent-upload/index.js`
- Modify: `miniprogram/miniprogram/pages/parent-upload/index.wxml`
- Modify: `miniprogram/miniprogram/pages/parent-upload/index.wxss`
- Test: `miniprogram/miniprogram/pages/parent-upload/index.test.js`

- [ ] **Step 1: Write failing tests**

Add tests that cover:

```js
test('onShow auto-selects the only binding when upload opens as a tab', async () => {
  const page = createPage();
  page.options = {};
  await page.onShow();
  assert.equal(page.data.binding.id, 21);
  assert.equal(page.data.needsBindingSelection, false);
});

test('onShow asks the parent to choose a child when multiple bindings exist and no current child is stored', async () => {
  const page = createPageWithBindings([{ id: 21 }, { id: 22 }]);
  page.options = {};
  await page.onShow();
  assert.equal(page.data.binding, null);
  assert.equal(page.data.needsBindingSelection, true);
});

test('selectUploadBinding switches upload context without navigating away', async () => {
  const page = createPageWithBindings([{ id: 21 }, { id: 22 }]);
  page.options = {};
  await page.onShow();
  await page.selectUploadBinding({ currentTarget: { dataset: { bindingId: '22' } } });
  assert.equal(page.data.binding.id, 22);
  assert.equal(page.data.needsBindingSelection, false);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
node --test miniprogram/miniprogram/pages/parent-upload/index.test.js
```

Expected: fail because `needsBindingSelection` and `selectUploadBinding()` are missing.

- [ ] **Step 3: Implement minimal selection behavior**

Add data fields:

```js
bindings: [],
needsBindingSelection: false,
```

In `onShow()`:

- Load `bindings` as before.
- Resolve binding by URL `bindingId`, current stored id, or single binding.
- Set `needsBindingSelection` to true only when multiple bindings exist and no binding is resolved.
- Keep existing restore/task logic only when `binding` exists.

Add:

```js
async selectUploadBinding(event) {
  const bindingId = Number(event.currentTarget.dataset.bindingId || 0);
  const binding = this.data.bindings.find((item) => item.id === bindingId) || null;
  if (!binding) {
    return;
  }
  setCurrentParentBindingId(wx, binding.id);
  const showPrimaryTopicCategory = isPrimarySchoolBinding(binding);
  this.setData({ binding, needsBindingSelection: false, showPrimaryTopicCategory, errorMessage: '' });
  if (showPrimaryTopicCategory) {
    const session = app.globalData.parentSession;
    await this.refreshTopicCategoryOptions(session && session.openId);
  }
  const session = app.globalData.parentSession;
  await this.restoreAcceptedUploadTasks(session && session.openId, binding);
}
```

- [ ] **Step 4: Update WXML/WXSS states**

Before `wx:if="{{binding}}"`, add:

- No binding empty state with a button `去我的绑定孩子` using `bindtap="goMySection"`.
- Multi-child chooser card with buttons bound to `selectUploadBinding`.

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
node --test miniprogram/miniprogram/pages/parent-upload/index.test.js
```

Expected: all tests pass.

---

### Task 4: Guardrails, Docs, and Integration

**Files:**
- Modify: `scripts/ralph/miniprogram_visual_polish_proof.sh` if needed
- Modify: `handoff.md`
- Modify: `miniprogram/handoff.md`

- [ ] **Step 1: Run visual proof to find stale contracts**

Run:

```bash
scripts/ralph/miniprogram_visual_polish_proof.sh
```

Expected: pass, or fail only on stale expectations that still require child-card `上传错题`.

- [ ] **Step 2: Update stale visual proof expectations if needed**

If it fails on old home-page action hierarchy, update it to expect:

- `我的孩子`.
- `设置当前上传孩子`.
- No `上传错题` inside `parent-home`.
- Bottom tabBar exists in `app.json`.

- [ ] **Step 3: Run final proof through a temporary script**

Create and run `/tmp/xingrun_miniprogram_parent_two_tabs_proof.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Users/ark.mini/Desktop/Xingrun-Website/.worktrees/miniprogram-parent-two-tabs
node --test \
  miniprogram/miniprogram/parent-only-scope.test.js \
  miniprogram/miniprogram/utils/parentApi.test.js \
  miniprogram/miniprogram/pages/parent-home/index.test.js \
  miniprogram/miniprogram/pages/parent-upload/index.test.js
scripts/ralph/miniprogram_visual_polish_proof.sh
scripts/ralph/miniprogram_upload_stability_proof.sh
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 4: Update handoff**

Update both handoff files with the final state:

- Two bottom tabs are implemented.
- `我的` sets current upload child and binds more children.
- `拍照上传` supports no-`bindingId` tab entry and child selection.
- Remaining risk is WeChat DevTools/real-device tabBar smoke.

- [ ] **Step 5: Commit implementation**

Run:

```bash
git status --short
git add miniprogram/miniprogram/app.json miniprogram/miniprogram/utils/parentApi.js miniprogram/miniprogram/utils/parentApi.test.js miniprogram/miniprogram/pages/parent-home/index.js miniprogram/miniprogram/pages/parent-home/index.wxml miniprogram/miniprogram/pages/parent-home/index.wxss miniprogram/miniprogram/pages/parent-home/index.test.js miniprogram/miniprogram/pages/parent-upload/index.js miniprogram/miniprogram/pages/parent-upload/index.wxml miniprogram/miniprogram/pages/parent-upload/index.wxss miniprogram/miniprogram/pages/parent-upload/index.test.js miniprogram/miniprogram/parent-only-scope.test.js scripts/ralph/miniprogram_visual_polish_proof.sh handoff.md miniprogram/handoff.md
git commit -m "feat: split parent mini program into two tabs"
```

- [ ] **Step 6: Merge back to develop and cleanup**

From the main workspace:

```bash
git switch develop
git merge --no-ff feature/miniprogram-parent-two-tabs
git branch -d feature/miniprogram-parent-two-tabs
git worktree remove .worktrees/miniprogram-parent-two-tabs
```

Expected: implementation commit history is preserved on `develop`, feature branch and worktree are removed.
