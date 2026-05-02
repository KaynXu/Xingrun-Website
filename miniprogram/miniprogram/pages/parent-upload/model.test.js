const assert = require('node:assert/strict');
const test = require('node:test');

const {
  buildUploadJobs,
  buildImageRotationPlan,
  buildUploadExportPlan,
  buildUploadTaskSummary,
  appendLocalImages,
  addManualBoxToImage,
  buildBoxTouchFrame,
  getSubmitBlockers,
  normalizeDisplayBoxFrame,
  rotateImageBoxesClockwise,
} = require('./model');

test('appendLocalImages keeps existing images and appends new ones', () => {
  const next = appendLocalImages([
    { id: 'img_1', localPath: 'a.jpg', boxes: [] },
  ], ['b.jpg', 'c.jpg']);

  assert.equal(next.length, 3);
  assert.equal(next[0].localPath, 'a.jpg');
  assert.equal(next[2].localPath, 'c.jpg');
  assert.deepEqual(next[1], {
    id: next[1].id,
    localPath: 'b.jpg',
    contentVersion: 0,
    boxes: [],
    activeBoxId: '',
  });
});

test('getSubmitBlockers reports images with zero boxes', () => {
  const blockers = getSubmitBlockers([
    { id: 'img_1', localPath: 'a.jpg', boxes: [{ id: 'box_1', childReasonText: '我审题没看完' }] },
    { id: 'img_2', localPath: 'b.jpg', boxes: [] },
    { id: 'img_3', localPath: 'c.jpg', boxes: [{ id: 'box_2' }] },
    { id: 'img_4', localPath: 'd.jpg', boxes: [{ id: 'box_4', childReasonText: '   ' }] },
  ]);

  assert.deepEqual(blockers, {
    emptyImageIds: ['img_2'],
    missingReasonBoxIds: [],
  });
});

test('addManualBoxToImage appends a manual box and selects it', () => {
  const next = addManualBoxToImage({
    id: 'img_1',
    localPath: 'a.jpg',
    boxes: [],
    activeBoxId: '',
  });

  assert.equal(next.boxes.length, 1);
  assert.equal(next.boxes[0].source, 'manual');
  assert.equal(next.activeBoxId, next.boxes[0].id);
  assert.equal(next.boxes[0].childReasonText, '');
  assert.equal(next.boxes[0].topicCategory, '未分类');
});

test('buildUploadJobs creates one upload job per box across all images', () => {
  const jobs = buildUploadJobs([
    {
      id: 'img_1',
      localPath: 'a.jpg',
      boxes: [
        { id: 'box_1', x: 0.1, y: 0.2, width: 0.4, height: 0.3, childReasonText: '第一题是我没审清楚', topicCategory: '行程' },
        { id: 'box_2', x: 0.55, y: 0.5, width: 0.3, height: 0.22, childReasonText: '第二题是我算错了' },
      ],
    },
    {
      id: 'img_2',
      localPath: 'b.jpg',
      boxes: [
        { id: 'box_3', x: 0.15, y: 0.18, width: 0.5, height: 0.28, childReasonText: '第三题单位换算漏了', topicCategory: '周期问题' },
      ],
    },
  ]);

  assert.equal(jobs.length, 3);
  assert.equal(jobs[0].imageId, 'img_1');
  assert.equal(jobs[2].boxId, 'box_3');
  assert.equal(jobs[2].localPath, 'b.jpg');
  assert.equal(jobs[1].childRawReasonText, '第二题是我算错了');
  assert.equal(jobs[0].topicCategory, '行程');
  assert.equal(jobs[1].topicCategory, '未分类');
  assert.equal(jobs[2].topicCategory, '周期问题');
});

test('buildUploadJobs falls back to text mode when a voice box has no recording file', () => {
  const jobs = buildUploadJobs([
    {
      id: 'img_1',
      localPath: 'a.jpg',
      boxes: [
        {
          id: 'box_1',
          x: 0.1,
          y: 0.2,
          width: 0.4,
          height: 0.3,
          childReasonInputMode: 'voice',
          voiceFilePath: '',
        },
      ],
    },
  ]);

  assert.equal(jobs.length, 1);
  assert.equal(jobs[0].childReasonInputMode, 'text');
  assert.equal(jobs[0].voiceFilePath, '');
});

test('buildUploadTaskSummary reports partial failure when some accepted tasks succeed', () => {
  const summary = buildUploadTaskSummary([
    { id: 1, status: 'ready' },
    { id: 2, status: 'failed', error_message: '题目识别失败，请重新拍清楚一点' },
  ]);

  assert.deepEqual(summary, {
    state: 'partial_failed',
    title: '部分识别失败',
    description: '1 条识别失败：题目识别失败，请重新拍清楚一点',
    readyCount: 1,
    failedCount: 1,
    pendingCount: 0,
  });
});

test('buildUploadTaskSummary reports failed when every accepted task fails', () => {
  const summary = buildUploadTaskSummary([
    { id: 1, status: 'failed', error_message: '题图太模糊' },
    { id: 2, status: 'failed', error_message: '题图太模糊' },
  ]);

  assert.deepEqual(summary, {
    state: 'failed',
    title: '识别失败',
    description: '2 条识别失败：题图太模糊',
    readyCount: 0,
    failedCount: 2,
    pendingCount: 0,
  });
});

test('buildUploadTaskSummary reports background processing after the polling window ends', () => {
  const summary = buildUploadTaskSummary([
    { id: 1, status: 'ready' },
    { id: 2, status: 'processing' },
  ], { background: true });

  assert.deepEqual(summary, {
    state: 'background',
    title: '后台继续识别',
    description: '已完成 1 条，还有 1 条在后台继续识别，稍后可回错题本查看。',
    readyCount: 1,
    failedCount: 0,
    pendingCount: 1,
  });
});

test('buildUploadTaskSummary reports ready only after every task is ready', () => {
  assert.deepEqual(buildUploadTaskSummary([
    { id: 1, status: 'ready' },
    { id: 2, status: 'ready' },
  ]), {
    state: 'ready',
    title: '识别完成',
    description: '本次 2 条错题已加入错题本。',
    readyCount: 2,
    failedCount: 0,
    pendingCount: 0,
  });

  assert.deepEqual(buildUploadTaskSummary([
    { id: 1, status: 'ready' },
    { id: 2, status: 'processing' },
  ]), {
    state: 'pending',
    title: '正在识别',
    description: '已完成 1 条，还有 1 条正在服务器识别。',
    readyCount: 1,
    failedCount: 0,
    pendingCount: 1,
  });
});

test('buildImageRotationPlan swaps canvas bounds for clockwise quarter turns', () => {
  const plan = buildImageRotationPlan({
    width: 1200,
    height: 900,
    quarterTurns: 1,
  });

  assert.deepEqual(plan, {
    canvasWidth: 900,
    canvasHeight: 1200,
    translateX: 900,
    translateY: 0,
    rotationRadians: Math.PI / 2,
    backgroundColor: '#ffffff',
  });
});

test('buildImageRotationPlan normalizes repeated clockwise turns', () => {
  const plan = buildImageRotationPlan({
    width: 1200,
    height: 900,
    quarterTurns: 5,
  });

  assert.deepEqual(plan, {
    canvasWidth: 900,
    canvasHeight: 1200,
    translateX: 900,
    translateY: 0,
    rotationRadians: Math.PI / 2,
    backgroundColor: '#ffffff',
  });
});

test('buildUploadExportPlan limits oversized crops before upload', () => {
  const plan = buildUploadExportPlan({
    cropWidth: 3000,
    cropHeight: 4200,
  });

  assert.deepEqual(plan, {
    outputWidth: 1280,
    outputHeight: 1792,
    quality: 0.82,
  });
});

test('buildBoxTouchFrame lets parents shrink a crop box to a small printed question', () => {
  const frame = buildBoxTouchFrame({
    mode: 'resize-se',
    startLeft: 10,
    startTop: 20,
    startWidth: 180,
    startHeight: 120,
    deltaX: -400,
    deltaY: -400,
    imageLeft: 0,
    imageTop: 0,
    imageWidth: 240,
    imageHeight: 320,
  });

  assert.deepEqual(frame, {
    left: 10,
    top: 20,
    width: 16,
    height: 16,
  });
});

test('normalizeDisplayBoxFrame saves small crop boxes without forcing eight percent of the image', () => {
  const box = normalizeDisplayBoxFrame({
    left: 10,
    top: 20,
    width: 16,
    height: 16,
    imageLeft: 0,
    imageTop: 0,
    imageWidth: 240,
    imageHeight: 320,
  });

  assert.deepEqual(box, {
    x: 10 / 240,
    y: 20 / 320,
    width: 16 / 240,
    height: 16 / 320,
  });
});

test('rotateImageBoxesClockwise keeps the same boxes in the rotated coordinate system', () => {
  const next = rotateImageBoxesClockwise({
    id: 'img_1',
    localPath: 'a.jpg',
    contentVersion: 0,
    boxes: [
      { id: 'box_1', x: 0.1, y: 0.2, width: 0.4, height: 0.3 },
      { id: 'box_2', x: 0.55, y: 0.1, width: 0.2, height: 0.25 },
    ],
    activeBoxId: 'box_2',
  });

  assert.deepEqual(next.boxes, [
    { id: 'box_1', x: 0.5, y: 0.1, width: 0.3, height: 0.4 },
    { id: 'box_2', x: 0.65, y: 0.55, width: 0.25, height: 0.2 },
  ]);
  assert.equal(next.activeBoxId, 'box_2');
  assert.equal(next.contentVersion, 1);
});

test('rotateImageBoxesClockwise keeps narrow boxes after parents adjust small questions', () => {
  const next = rotateImageBoxesClockwise({
    id: 'img_1',
    localPath: 'a.jpg',
    contentVersion: 0,
    boxes: [
      { id: 'box_1', x: 0.2, y: 0.3, width: 0.02, height: 0.03 },
    ],
    activeBoxId: 'box_1',
  });

  assert.equal(next.boxes[0].id, 'box_1');
  assert.equal(Math.round(next.boxes[0].x * 100), 67);
  assert.equal(next.boxes[0].y, 0.2);
  assert.equal(next.boxes[0].width, 0.03);
  assert.equal(next.boxes[0].height, 0.02);
});
