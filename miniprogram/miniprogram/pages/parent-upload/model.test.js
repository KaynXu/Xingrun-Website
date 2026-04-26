const assert = require('node:assert/strict');
const test = require('node:test');

const {
  buildUploadJobs,
  buildImageRotationPlan,
  buildUploadExportPlan,
  appendLocalImages,
  addManualBoxToImage,
  getSubmitBlockers,
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
});

test('buildUploadJobs creates one upload job per box across all images', () => {
  const jobs = buildUploadJobs([
    {
      id: 'img_1',
      localPath: 'a.jpg',
      boxes: [
        { id: 'box_1', x: 0.1, y: 0.2, width: 0.4, height: 0.3, childReasonText: '第一题是我没审清楚' },
        { id: 'box_2', x: 0.55, y: 0.5, width: 0.3, height: 0.22, childReasonText: '第二题是我算错了' },
      ],
    },
    {
      id: 'img_2',
      localPath: 'b.jpg',
      boxes: [
        { id: 'box_3', x: 0.15, y: 0.18, width: 0.5, height: 0.28, childReasonText: '第三题单位换算漏了' },
      ],
    },
  ]);

  assert.equal(jobs.length, 3);
  assert.equal(jobs[0].imageId, 'img_1');
  assert.equal(jobs[2].boxId, 'box_3');
  assert.equal(jobs[2].localPath, 'b.jpg');
  assert.equal(jobs[1].childRawReasonText, '第二题是我算错了');
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
