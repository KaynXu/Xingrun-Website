# Parent Upload Crop + AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the parent upload page from single-image direct upload to mobile-friendly multi-image crop, optional AI box suggestion, and per-box batch submission.

**Architecture:** Keep the existing `pages/parent-upload` route, add a small pure-state helper for image/box management, add one new bridge API for AI box detection, and keep final uploads on the existing `/wechat/parent/wrong-questions` endpoint by cropping each confirmed box into its own temp file before submit. The backend bridge stays thin: accept one file, persist it locally, forward the generated file URL to the website AI endpoint, and return box candidates without judging quality.

**Tech Stack:** WeChat Mini Program page JS/WXML/WXSS, Node `node:test` for mini program helpers, Express + TypeScript bridge backend, `tsx` test runner for backend route tests.

---

## File Structure

**Create**

- `docs/superpowers/plans/2026-04-09-parent-upload-crop-ai-plan.md`
- `miniprogram/pages/parent-upload/model.js`
- `miniprogram/pages/parent-upload/model.test.js`

**Modify**

- `miniprogram/pages/parent-upload/index.js`
- `miniprogram/pages/parent-upload/index.wxml`
- `miniprogram/pages/parent-upload/index.wxss`
- `miniprogram/utils/parentApi.js`
- `miniprogram/utils/parentApi.test.js`
- `miniprogram/parent-only-scope.test.js`
- `backend/src/website-client.ts`
- `backend/src/index.ts`
- `backend/src/parent-wechat-bridge.test.ts`
- `handoff.md`

**Responsibility Map**

- `miniprogram/pages/parent-upload/model.js`: pure helpers for image queue state, AI state, box normalization, and submit blocking checks.
- `miniprogram/pages/parent-upload/index.js`: page lifecycle, image selection/append, AI trigger, drag interactions, crop-and-submit orchestration.
- `miniprogram/pages/parent-upload/index.wxml`: mobile single-column UI, thumbnail strip, crop stage, action buttons, AI status messaging.
- `miniprogram/pages/parent-upload/index.wxss`: responsive mobile layout and draggable box handles.
- `miniprogram/utils/parentApi.js`: HTTP helpers for AI box detection and final upload.
- `backend/src/index.ts`: new `/wechat/parent/wrong-question-boxes` route.
- `backend/src/website-client.ts`: website bridge helper for wrong-question box detection.

## Task 1: Add backend AI box bridge route

**Files:**
- Modify: `backend/src/parent-wechat-bridge.test.ts`
- Modify: `backend/src/website-client.ts`
- Modify: `backend/src/index.ts`
- Test: `backend/src/parent-wechat-bridge.test.ts`

- [ ] **Step 1: Write the failing backend bridge test**

Add this test to `backend/src/parent-wechat-bridge.test.ts`:

```ts
test('parent AI box bridge stores the file and forwards its image url to the website detector', async (t) => {
  const originalFetch = globalThis.fetch;
  const uploadedFiles: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-question-boxes') {
      const body = JSON.parse(String(init?.body || '{}'));
      assert.match(body.image_url, /^http:\/\/127\.0\.0\.1:\d+\/files\/.+/);
      uploadedFiles.push(String(body.image_url).split('/files/')[1]);
      return createJsonResponse({
        boxes: [
          { x: 0.1, y: 0.2, width: 0.4, height: 0.3 },
          { x: 0.55, y: 0.5, width: 0.3, height: 0.22 },
        ],
      });
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;
    const formData = new FormData();
    formData.set('file', new Blob(['mock-image']), 'wrong-question-box.txt');

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-question-boxes`, {
      method: 'POST',
      body: formData,
    });

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.boxes.length, 2);
    assert.deepEqual(payload.boxes[0], { x: 0.1, y: 0.2, width: 0.4, height: 0.3 });

    const uploadedPath = uploadedFiles[0] ? path.join(UPLOADS_DIR, uploadedFiles[0]) : '';
    assert.ok(uploadedPath);
    assert.equal(fs.existsSync(uploadedPath), true);

    t.after(() => {
      if (uploadedPath) {
        fs.rmSync(uploadedPath, { force: true });
      }
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
```

- [ ] **Step 2: Run the backend route test and verify it fails**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend
node --import tsx --test src/parent-wechat-bridge.test.ts
```

Expected: FAIL on `POST /wechat/parent/wrong-question-boxes` because the route and website client helper do not exist yet.

- [ ] **Step 3: Write the minimal backend implementation**

Add this helper to `backend/src/website-client.ts`:

```ts
export interface WebsiteWrongQuestionBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export async function detectWechatWrongQuestionBoxesOnWebsite(input: {
  imageUrl: string;
}) {
  return requestWebsite<{ boxes: WebsiteWrongQuestionBox[] }>('/api/wechat/wrong-question-boxes', {
    method: 'POST',
    body: {
      image_url: input.imageUrl,
    },
  });
}
```

Update the imports in `backend/src/index.ts` and add this route next to the existing upload route:

```ts
  app.post('/wechat/parent/wrong-question-boxes', upload.single('file'), async (req, res) => {
    const uploadedImageUrl = req.file ? `${getBaseUrl(req.get('host'))}/files/${req.file.filename}` : '';
    const imageUrl = uploadedImageUrl || String(req.body?.imageUrl ?? req.body?.image_url ?? '').trim();

    if (!imageUrl) {
      res.status(400).json({ error: 'file required' });
      return;
    }

    try {
      const payload = await detectWechatWrongQuestionBoxesOnWebsite({ imageUrl });
      res.json(payload);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });
```

- [ ] **Step 4: Run the backend route test and verify it passes**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend
node --import tsx --test src/parent-wechat-bridge.test.ts
```

Expected: PASS with 5 passing tests, including the new AI box bridge case.

- [ ] **Step 5: Commit the backend bridge slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
git add backend/src/index.ts backend/src/website-client.ts backend/src/parent-wechat-bridge.test.ts
git commit -m "feat: add parent wrong-question box bridge"
```

## Task 2: Add mini program API helper for AI box detection

**Files:**
- Modify: `miniprogram/utils/parentApi.test.js`
- Modify: `miniprogram/utils/parentApi.js`
- Test: `miniprogram/utils/parentApi.test.js`

- [ ] **Step 1: Write the failing mini program API test**

Add this test to `miniprogram/utils/parentApi.test.js`:

```js
test('detectParentWrongQuestionBoxes parses the AI box bridge response', async () => {
  const wxApi = {
    uploadFile({ url, success }) {
      if (url.endsWith('/wechat/parent/wrong-question-boxes')) {
        success({
          statusCode: 200,
          data: JSON.stringify({
            boxes: [
              { x: 0.1, y: 0.2, width: 0.4, height: 0.3 },
              { x: 0.55, y: 0.5, width: 0.3, height: 0.22 },
            ],
          }),
        });
        return;
      }

      throw new Error(`Unexpected upload url: ${url}`);
    },
  };

  const payload = await detectParentWrongQuestionBoxes(wxApi, 'https://example.com', {
    filePath: '/tmp/mock-image.png',
  });

  assert.equal(payload.boxes.length, 2);
  assert.deepEqual(payload.boxes[1], { x: 0.55, y: 0.5, width: 0.3, height: 0.22 });
});
```

Also update the import list at the top:

```js
  detectParentWrongQuestionBoxes,
```

- [ ] **Step 2: Run the mini program API test and verify it fails**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
node --test miniprogram/utils/parentApi.test.js
```

Expected: FAIL because `detectParentWrongQuestionBoxes` is not exported yet.

- [ ] **Step 3: Write the minimal API helper**

Add these helpers to `miniprogram/utils/parentApi.js`:

```js
function normalizeWrongQuestionBox(box) {
  const source = box && typeof box === 'object' ? box : {};
  return {
    x: Number(source.x || 0) || 0,
    y: Number(source.y || 0) || 0,
    width: Number(source.width || 0) || 0,
    height: Number(source.height || 0) || 0,
  };
}

async function detectParentWrongQuestionBoxes(wxApi, serverUrl, params) {
  const payload = await uploadFile(wxApi, {
    url: `${serverUrl}/wechat/parent/wrong-question-boxes`,
    filePath: params.filePath,
    name: 'file',
    formData: {},
  });

  return {
    boxes: Array.isArray(payload.boxes) ? payload.boxes.map(normalizeWrongQuestionBox) : [],
  };
}
```

Export the helper:

```js
  detectParentWrongQuestionBoxes,
```

- [ ] **Step 4: Run the API test and verify it passes**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
node --test miniprogram/utils/parentApi.test.js
```

Expected: PASS with 6 passing tests.

- [ ] **Step 5: Commit the mini program API slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
git add miniprogram/utils/parentApi.js miniprogram/utils/parentApi.test.js
git commit -m "feat: add parent AI box api helper"
```

## Task 3: Create pure upload model helpers for images, boxes, and submit gating

**Files:**
- Create: `miniprogram/pages/parent-upload/model.js`
- Create: `miniprogram/pages/parent-upload/model.test.js`
- Test: `miniprogram/pages/parent-upload/model.test.js`

- [ ] **Step 1: Write the failing pure-model tests**

Create `miniprogram/pages/parent-upload/model.test.js` with:

```js
const assert = require('node:assert/strict');
const test = require('node:test');

const {
  appendLocalImages,
  applyAiBoxesToImage,
  addManualBoxToImage,
  getSubmitBlockers,
} = require('./model');

test('appendLocalImages keeps existing images and appends new ones', () => {
  const next = appendLocalImages([
    { id: 'img_1', localPath: 'a.jpg', aiStatus: 'idle', boxes: [] },
  ], ['b.jpg', 'c.jpg']);

  assert.equal(next.length, 3);
  assert.equal(next[0].localPath, 'a.jpg');
  assert.equal(next[2].localPath, 'c.jpg');
});

test('applyAiBoxesToImage marks empty results without inventing quality scores', () => {
  const imageItem = { id: 'img_1', localPath: 'a.jpg', aiStatus: 'running', boxes: [] };
  const next = applyAiBoxesToImage(imageItem, []);

  assert.equal(next.aiStatus, 'empty');
  assert.equal(next.boxes.length, 0);
});

test('getSubmitBlockers reports images with zero boxes or running AI work', () => {
  const blockers = getSubmitBlockers([
    { id: 'img_1', localPath: 'a.jpg', aiStatus: 'done', boxes: [{ id: 'box_1' }] },
    { id: 'img_2', localPath: 'b.jpg', aiStatus: 'empty', boxes: [] },
    { id: 'img_3', localPath: 'c.jpg', aiStatus: 'running', boxes: [{ id: 'box_2' }] },
  ]);

  assert.deepEqual(blockers, {
    emptyImageIds: ['img_2'],
    runningImageIds: ['img_3'],
  });
});

test('addManualBoxToImage appends a manual box and selects it', () => {
  const next = addManualBoxToImage({
    id: 'img_1',
    localPath: 'a.jpg',
    aiStatus: 'empty',
    boxes: [],
    activeBoxId: '',
  });

  assert.equal(next.boxes.length, 1);
  assert.equal(next.boxes[0].source, 'manual');
  assert.equal(next.activeBoxId, next.boxes[0].id);
});
```

- [ ] **Step 2: Run the model tests and verify they fail**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
node --test miniprogram/pages/parent-upload/model.test.js
```

Expected: FAIL because `model.js` does not exist yet.

- [ ] **Step 3: Write the minimal model helper implementation**

Create `miniprogram/pages/parent-upload/model.js` with:

```js
let imageCounter = 0;
let boxCounter = 0;

function createDefaultBox(source) {
  boxCounter += 1;
  return {
    id: `box_${boxCounter}`,
    source,
    x: 0.15,
    y: 0.18,
    width: 0.7,
    height: 0.28,
  };
}

function appendLocalImages(imageItems, filePaths) {
  const list = Array.isArray(imageItems) ? imageItems.slice() : [];
  const nextPaths = Array.isArray(filePaths) ? filePaths : [];
  return list.concat(nextPaths.map((localPath) => {
    imageCounter += 1;
    return {
      id: `img_${imageCounter}`,
      localPath,
      aiStatus: 'idle',
      aiErrorMessage: '',
      boxes: [],
      activeBoxId: '',
    };
  }));
}

function applyAiBoxesToImage(imageItem, boxes) {
  const nextBoxes = Array.isArray(boxes)
    ? boxes.map((box) => ({ ...createDefaultBox('ai'), ...box, source: 'ai' }))
    : [];
  return {
    ...imageItem,
    aiStatus: nextBoxes.length > 0 ? 'done' : 'empty',
    aiErrorMessage: '',
    boxes: nextBoxes,
    activeBoxId: nextBoxes[0] ? nextBoxes[0].id : '',
  };
}

function addManualBoxToImage(imageItem) {
  const box = createDefaultBox('manual');
  return {
    ...imageItem,
    aiStatus: imageItem.aiStatus === 'empty' ? 'done' : imageItem.aiStatus,
    boxes: (imageItem.boxes || []).concat(box),
    activeBoxId: box.id,
  };
}

function getSubmitBlockers(imageItems) {
  const list = Array.isArray(imageItems) ? imageItems : [];
  return {
    emptyImageIds: list.filter((item) => !(item.boxes || []).length).map((item) => item.id),
    runningImageIds: list.filter((item) => item.aiStatus === 'running').map((item) => item.id),
  };
}

module.exports = {
  appendLocalImages,
  applyAiBoxesToImage,
  addManualBoxToImage,
  getSubmitBlockers,
};
```

- [ ] **Step 4: Run the model tests and verify they pass**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
node --test miniprogram/pages/parent-upload/model.test.js
```

Expected: PASS with 4 passing tests.

- [ ] **Step 5: Commit the pure-model slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
git add miniprogram/pages/parent-upload/model.js miniprogram/pages/parent-upload/model.test.js
git commit -m "feat: add parent upload image box model"
```

## Task 4: Refactor the upload page UI for multi-image mobile crop editing

**Files:**
- Modify: `miniprogram/pages/parent-upload/index.js`
- Modify: `miniprogram/pages/parent-upload/index.wxml`
- Modify: `miniprogram/pages/parent-upload/index.wxss`
- Modify: `miniprogram/parent-only-scope.test.js`
- Test: `miniprogram/parent-only-scope.test.js`

- [ ] **Step 1: Write the failing regression test for the new upload UI copy**

Add this test to `miniprogram/parent-only-scope.test.js`:

```js
test('parent upload page exposes crop-first multi-image controls', () => {
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');

  assert.equal(uploadTemplate.includes('AI 框选'), true);
  assert.equal(uploadTemplate.includes('补加框'), true);
  assert.equal(uploadTemplate.includes('删除当前'), true);
  assert.equal(uploadTemplate.includes('拍照或从相册里选一张图片'), false);
});
```

- [ ] **Step 2: Run the regression test and verify it fails**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
node --test miniprogram/parent-only-scope.test.js
```

Expected: FAIL because the current page still contains single-image wording and no AI/box controls.

- [ ] **Step 3: Write the minimal page integration**

Update `miniprogram/pages/parent-upload/index.js` to import the new helpers and replace single-file state:

```js
const {
  appendLocalImages,
  applyAiBoxesToImage,
  addManualBoxToImage,
  getSubmitBlockers,
} = require('./model');

data: {
  binding: null,
  imageItems: [],
  selectedImageId: '',
  currentImage: null,
  parentNote: '',
  submitting: false,
  successRecordIds: [],
  errorMessage: '',
}
```

Add the new actions:

```js
chooseImages() {
  wx.chooseImage({
    count: 9,
    sizeType: ['compressed'],
    sourceType: ['camera', 'album'],
    success: (response) => {
      const filePaths = response.tempFilePaths || [];
      const imageItems = appendLocalImages(this.data.imageItems, filePaths);
      const selectedImageId = this.data.selectedImageId || (imageItems[0] && imageItems[0].id) || '';
      this.setData({
        imageItems,
        selectedImageId,
        currentImage: imageItems.find((item) => item.id === selectedImageId) || null,
        successRecordIds: [],
        errorMessage: '',
      });
    },
  });
},

selectImage(event) {
  const selectedImageId = String(event.currentTarget.dataset.imageId || '');
  this.setData({
    selectedImageId,
    currentImage: this.data.imageItems.find((item) => item.id === selectedImageId) || null,
  });
},

addManualBox() {
  const imageItems = this.data.imageItems.map((item) => (
    item.id === this.data.selectedImageId ? addManualBoxToImage(item) : item
  ));
  this.setData({ imageItems });
},

removeActiveBox() {
  const imageItems = this.data.imageItems.map((item) => {
    if (item.id !== this.data.selectedImageId) {
      return item;
    }
    const boxes = (item.boxes || []).filter((box) => box.id !== item.activeBoxId);
    return {
      ...item,
      boxes,
      activeBoxId: boxes[0] ? boxes[0].id : '',
      aiStatus: boxes.length ? item.aiStatus : 'empty',
    };
  });
  this.setData({ imageItems });
},
```

Update `miniprogram/pages/parent-upload/index.wxml` to the mobile single-column structure:

```xml
<text class="hero-subtitle">拍照、连续追加或从相册多选，再框出每一道错题后统一提交给老师。</text>
<button class="ghost-btn" bindtap="chooseImages">{{imageItems.length ? '继续拍照 / 继续选图' : '拍照 / 选择图片'}}</button>

<scroll-view wx:if="{{imageItems.length}}" class="thumb-strip" scroll-x="true">
  <view
    wx:for="{{imageItems}}"
    wx:key="id"
    class="thumb-item {{item.id === selectedImageId ? 'thumb-item-active' : ''}}"
    data-image-id="{{item.id}}"
    bindtap="selectImage"
  >
    <image class="thumb-image" src="{{item.localPath}}" mode="aspectFill" />
  </view>
</scroll-view>

<view wx:if="{{imageItems.length}}" class="crop-stage">
  <image class="preview-image" src="{{currentImage.localPath}}" mode="widthFix" />
  <canvas canvas-id="cropCanvas" class="hidden-crop-canvas"></canvas>
  <view class="action-row">
    <button class="ghost-btn compact-btn" bindtap="addManualBox">补加框</button>
    <button class="ghost-btn compact-btn" bindtap="removeActiveBox">删除当前</button>
    <button class="ghost-btn compact-btn" bindtap="runAiBoxes">AI 框选</button>
  </view>
</view>
```

Update `miniprogram/pages/parent-upload/index.wxss` with the new mobile classes:

```css
.thumb-strip {
  white-space: nowrap;
  margin-top: 18rpx;
}

.thumb-item {
  display: inline-block;
  width: 116rpx;
  height: 116rpx;
  margin-right: 12rpx;
  border-radius: 20rpx;
  overflow: hidden;
  border: 3rpx solid transparent;
}

.thumb-item-active {
  border-color: #2375d8;
}

.action-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12rpx;
}

.hidden-crop-canvas {
  position: fixed;
  left: -9999rpx;
  top: -9999rpx;
  width: 1px;
  height: 1px;
}

.compact-btn {
  margin-top: 0;
  font-size: 24rpx;
}
```

- [ ] **Step 4: Run the regression test and verify it passes**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
node --test miniprogram/parent-only-scope.test.js
```

Expected: PASS with 6 passing tests.

- [ ] **Step 5: Commit the mobile upload page slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
git add miniprogram/pages/parent-upload/index.js miniprogram/pages/parent-upload/index.wxml miniprogram/pages/parent-upload/index.wxss miniprogram/parent-only-scope.test.js
git commit -m "feat: add parent upload multi-image crop ui"
```

## Task 5: Wire AI results, submit validation, and per-box batch upload

**Files:**
- Modify: `miniprogram/pages/parent-upload/index.js`
- Modify: `miniprogram/utils/parentApi.test.js`
- Modify: `miniprogram/utils/parentApi.js`
- Modify: `miniprogram/pages/parent-upload/model.test.js`
- Test: `miniprogram/utils/parentApi.test.js`
- Test: `miniprogram/pages/parent-upload/model.test.js`

- [ ] **Step 1: Write the failing tests for submit blocking and AI box application**

Add this test to `miniprogram/pages/parent-upload/model.test.js`:

```js
test('applyAiBoxesToImage converts AI results into selectable boxes', () => {
  const next = applyAiBoxesToImage({
    id: 'img_1',
    localPath: 'a.jpg',
    aiStatus: 'running',
    boxes: [],
    activeBoxId: '',
  }, [
    { x: 0.1, y: 0.2, width: 0.4, height: 0.3 },
    { x: 0.55, y: 0.5, width: 0.3, height: 0.22 },
  ]);

  assert.equal(next.aiStatus, 'done');
  assert.equal(next.boxes.length, 2);
  assert.equal(next.activeBoxId, next.boxes[0].id);
});
```

Add this test to `miniprogram/utils/parentApi.test.js`:

```js
test('submitParentWrongQuestion sends parent note per cropped file submission', async () => {
  const calls = [];
  const wxApi = {
    uploadFile({ url, filePath, formData, success }) {
      calls.push({ url, filePath, formData });
      success({
        statusCode: 201,
        data: JSON.stringify({ record: { id: `record-${calls.length}` } }),
      });
    },
  };

  await submitParentWrongQuestion(wxApi, 'https://example.com', {
    openId: 'openid-parent-1',
    bindingId: 21,
    filePath: '/tmp/crop-1.png',
    parentNote: '第 1 题',
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].filePath, '/tmp/crop-1.png');
  assert.equal(calls[0].formData.parentNote, '第 1 题');
});
```

- [ ] **Step 2: Run the model and API tests and verify at least one fails**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
node --test miniprogram/pages/parent-upload/model.test.js
node --test miniprogram/utils/parentApi.test.js
```

Expected: the new test set fails before the page orchestration is finished.

- [ ] **Step 3: Write the minimal orchestration for AI and final submit**

In `miniprogram/pages/parent-upload/index.js`, add AI orchestration:

```js
async runAiBoxes() {
  const imageItems = this.data.imageItems.map((item) => ({
    ...item,
    aiStatus: 'running',
    aiErrorMessage: '',
  }));
  this.setData({ imageItems, errorMessage: '' });

  const queue = imageItems.slice();
  const workerCount = Math.min(3, queue.length);

  await Promise.all(new Array(workerCount).fill(null).map(async () => {
    while (queue.length) {
      const item = queue.shift();
      if (!item) {
        return;
      }

      try {
        const payload = await detectParentWrongQuestionBoxes(wx, app.globalData.serverUrl, {
          filePath: item.localPath,
        });
        const nextItems = this.data.imageItems.map((candidate) => (
          candidate.id === item.id ? applyAiBoxesToImage(candidate, payload.boxes) : candidate
        ));
        this.setData({
          imageItems: nextItems,
          currentImage: nextItems.find((candidate) => candidate.id === this.data.selectedImageId) || null,
        });
      } catch (error) {
        const nextItems = this.data.imageItems.map((candidate) => (
          candidate.id === item.id
            ? { ...candidate, aiStatus: 'failed', aiErrorMessage: error instanceof Error ? error.message : 'AI 框选失败' }
            : candidate
        ));
        this.setData({
          imageItems: nextItems,
          currentImage: nextItems.find((candidate) => candidate.id === this.data.selectedImageId) || null,
        });
      }
    }
  }));
}
```

Add submit blocking and batch upload:

```js
async submitUpload() {
  if (this.data.submitting) {
    return;
  }

  const blockers = getSubmitBlockers(this.data.imageItems);
  if (blockers.runningImageIds.length) {
    wx.showToast({ title: 'AI 还在处理中，请稍后提交', icon: 'none' });
    return;
  }
  if (blockers.emptyImageIds.length) {
    wx.showToast({ title: '还有图片未补框', icon: 'none' });
    return;
  }

  this.setData({ submitting: true, errorMessage: '' });

  try {
    const session = await ensureParentSession(wx, app.globalData.serverUrl);
    const successRecordIds = [];

    for (const imageItem of this.data.imageItems) {
      for (const box of imageItem.boxes) {
        const croppedPath = imageItem.localPath;
        const payload = await submitParentWrongQuestion(wx, app.globalData.serverUrl, {
          openId: session.openId,
          bindingId: this.data.binding.id,
          filePath: croppedPath,
          parentNote: this.data.parentNote,
        });
        successRecordIds.push((payload.record && payload.record.id) || '');
      }
    }

    this.setData({
      successRecordIds,
      imageItems: [],
      selectedImageId: '',
      currentImage: null,
      parentNote: '',
    });
  } catch (error) {
    this.setData({
      errorMessage: error instanceof Error ? error.message : '上传失败',
    });
  } finally {
    this.setData({ submitting: false });
  }
}
```

For the first green pass, keep `croppedPath = imageItem.localPath` so the state and batching land first. The actual crop export can be added immediately afterward inside the same task before final verification by replacing that one line with the canvas-generated temp file result.

Add the crop export helper in the same file:

```js
async exportBoxCrop(imageItem, box) {
  return imageItem.localPath;
}
```

Then replace:

```js
const croppedPath = await this.exportBoxCrop(imageItem, box);
```

- [ ] **Step 4: Finish the real crop export and run the focused tests**

Replace the stub with a real canvas export using the normalized box:

```js
async exportBoxCrop(imageItem, box) {
  const imageInfo = await new Promise((resolve, reject) => {
    wx.getImageInfo({
      src: imageItem.localPath,
      success: resolve,
      fail: reject,
    });
  });

  const cropX = Math.round(box.x * imageInfo.width);
  const cropY = Math.round(box.y * imageInfo.height);
  const cropWidth = Math.round(box.width * imageInfo.width);
  const cropHeight = Math.round(box.height * imageInfo.height);

  return new Promise((resolve, reject) => {
    const ctx = wx.createCanvasContext('cropCanvas', this);
    ctx.clearRect(0, 0, cropWidth, cropHeight);
    ctx.drawImage(imageItem.localPath, cropX, cropY, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);
    ctx.draw(false, () => {
      wx.canvasToTempFilePath({
        canvasId: 'cropCanvas',
        x: 0,
        y: 0,
        width: cropWidth,
        height: cropHeight,
        destWidth: cropWidth,
        destHeight: cropHeight,
        success: (response) => resolve(response.tempFilePath),
        fail: reject,
      }, this);
    });
  });
}
```

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
node --test miniprogram/pages/parent-upload/model.test.js
node --test miniprogram/utils/parentApi.test.js
node --test miniprogram/parent-only-scope.test.js
```

Expected: PASS on all three mini program test files.

- [ ] **Step 5: Commit the AI + batch submit slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
git add miniprogram/pages/parent-upload/index.js miniprogram/pages/parent-upload/model.test.js miniprogram/utils/parentApi.test.js miniprogram/utils/parentApi.js miniprogram/parent-only-scope.test.js
git commit -m "feat: add parent upload ai box submit flow"
```

## Task 6: Final verification and handoff docs

**Files:**
- Modify: `handoff.md`

- [ ] **Step 1: Run the full relevant verification set**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
node --test miniprogram/utils/parentApi.test.js
node --test miniprogram/pages/parent-upload/model.test.js
node --test miniprogram/parent-only-scope.test.js
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram/backend
node --import tsx --test src/parent-wechat-bridge.test.ts
```

Expected:

```text
pass 7 / fail 0   # miniprogram/utils/parentApi.test.js
pass 5 / fail 0   # miniprogram/pages/parent-upload/model.test.js
pass 6 / fail 0   # miniprogram/parent-only-scope.test.js
pass 5 / fail 0   # backend/src/parent-wechat-bridge.test.ts
```

- [ ] **Step 2: Update handoff.md with completed proof**

Append a new entry in `handoff.md` that includes:

```md
## 2026-04-09 Parent Upload Crop + AI Flow Implemented
- 已完成：
  - 家长上传页支持多图、同页框选、AI 框选、统一提交
  - 新增后端 AI 框选桥接接口
- proof：
  - `node --test miniprogram/utils/parentApi.test.js`
  - `node --test miniprogram/pages/parent-upload/model.test.js`
  - `node --test miniprogram/parent-only-scope.test.js`
  - `node --import tsx --test src/parent-wechat-bridge.test.ts`
```

- [ ] **Step 3: Commit the verification + handoff update**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-MiniProgram
git add handoff.md
git commit -m "docs: record parent upload crop ai verification"
```

## Self-Review

### Spec coverage

- Multi-image selection and continuous append: Task 3 + Task 4
- Single-image multi-question boxes: Task 3 + Task 5
- Same-page crop editing: Task 4 + Task 5
- AI button on all selected images: Task 1 + Task 2 + Task 5
- No AI quality judgment: Task 3 + Task 5
- Block submit on zero-box images: Task 3 + Task 5
- Mobile-first layout: Task 4

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every code-changing step includes a concrete code block.
- Every verification step includes an exact command.

### Type and naming consistency

- Backend route name is consistently `wrong-question-boxes`.
- Frontend API helper is consistently `detectParentWrongQuestionBoxes`.
- Page state field is consistently `imageItems`.
