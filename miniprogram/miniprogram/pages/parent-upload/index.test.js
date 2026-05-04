const assert = require('node:assert/strict');
const test = require('node:test');

function loadUploadPage(parentApi) {
  const pagePath = require.resolve('./index');
  const parentApiPath = require.resolve('../../utils/parentApi');
  const originalPage = global.Page;
  const originalGetApp = global.getApp;
  const originalParentApiCache = require.cache[parentApiPath];
  let pageConfig = null;

  delete require.cache[pagePath];
  require.cache[parentApiPath] = {
    id: parentApiPath,
    filename: parentApiPath,
    loaded: true,
    exports: parentApi,
  };
  global.getApp = () => ({
    globalData: {
      serverUrl: 'https://example.com',
    },
  });
  global.Page = (config) => {
    pageConfig = config;
  };

  try {
    require(pagePath);
  } finally {
    if (originalParentApiCache) {
      require.cache[parentApiPath] = originalParentApiCache;
    } else {
      delete require.cache[parentApiPath];
    }
    global.Page = originalPage;
    global.getApp = originalGetApp;
  }

  return pageConfig;
}

function createPageInstance(pageConfig, dataOverrides) {
  const updates = [];
  const page = {
    ...pageConfig,
    data: {
      ...JSON.parse(JSON.stringify(pageConfig.data)),
      ...dataOverrides,
    },
    setData(nextData, callback) {
      this.data = {
        ...this.data,
        ...nextData,
      };
      updates.push(nextData);
      if (typeof callback === 'function') {
        callback();
      }
    },
  };
  page.__updates = updates;
  page.waitForUploadTaskPoll = async () => {};
  return page;
}

function createReadyUploadData() {
  return {
    binding: {
      id: 21,
      studentName: 'Alice',
      className: '六年级 1 班',
    },
    imageItems: [
      {
        id: 'img_1',
        localPath: '/tmp/source.jpg',
        boxes: [
          {
            id: 'box_1',
            x: 0.1,
            y: 0.2,
            width: 0.4,
            height: 0.3,
            childReasonInputMode: 'voice',
            childReasonText: '我把单位看错了',
            voiceFilePath: '/tmp/reason.mp3',
            topicCategory: '计算',
          },
        ],
        activeBoxId: 'box_1',
      },
    ],
  };
}

function createTwoBoxUploadData() {
  const imageItem = {
    id: 'img_1',
    localPath: '/tmp/source.jpg',
    boxes: [
      {
        id: 'box_1',
        x: 0.1,
        y: 0.12,
        width: 0.36,
        height: 0.22,
        childReasonInputMode: 'text',
        childReasonText: '第一题没看清单位',
        topicCategory: '计算',
      },
      {
        id: 'box_2',
        x: 0.52,
        y: 0.58,
        width: 0.32,
        height: 0.2,
        childReasonInputMode: 'text',
        childReasonText: '第二题算错了',
        topicCategory: '几何',
      },
    ],
    activeBoxId: 'box_2',
  };
  return {
    binding: {
      id: 21,
      studentName: 'Alice',
      className: '六年级 1 班',
    },
    imageItems: [imageItem],
    selectedImageId: 'img_1',
    currentImage: imageItem,
    activeBox: imageItem.boxes[1],
  };
}

function withWx(testBody, wxOverrides) {
  const originalWx = global.wx;
  const toasts = [];
  global.wx = {
    showToast(payload) {
      toasts.push(payload);
    },
    ...(wxOverrides || {}),
  };
  return Promise.resolve()
    .then(() => testBody(toasts))
    .finally(() => {
      global.wx = originalWx;
    });
}

test('loadCurrentImage handles large portrait and landscape photos while switching images', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });
  const page = createPageInstance(pageConfig, {
    stageWidth: 300,
    stageHeight: 420,
    imageItems: [
      {
        id: 'img_portrait',
        localPath: '/tmp/large-portrait.jpg',
        boxes: [{ id: 'box_p', x: 0.2, y: 0.2, width: 0.4, height: 0.2 }],
        activeBoxId: 'box_p',
      },
      {
        id: 'img_landscape',
        localPath: '/tmp/large-landscape.jpg',
        boxes: [{ id: 'box_l', x: 0.15, y: 0.18, width: 0.5, height: 0.3 }],
        activeBoxId: 'box_l',
      },
    ],
    selectedImageId: 'img_portrait',
  });
  page.getImageInfo = async (src) => {
    if (src.includes('landscape')) {
      return { width: 4200, height: 3000 };
    }
    return { width: 3000, height: 4200 };
  };

  await page.loadCurrentImage();
  assert.equal(page.data.selectedImageId, 'img_portrait');
  assert.equal(page.data.activeBox.id, 'box_p');
  assert.equal(page.data.imageWidth, 300);
  assert.equal(page.data.imageHeight, 420);

  await page.selectImage({ currentTarget: { dataset: { imageId: 'img_landscape' } } });
  assert.equal(page.data.selectedImageId, 'img_landscape');
  assert.equal(page.data.activeBox.id, 'box_l');
  assert.equal(page.data.imageWidth, 300);
  assert.equal(page.data.imageHeight, 214);
  assert.equal(page.data.imageTop, 103);
});

test('rotateCurrentImageClockwise keeps the selected image and tiny selected box stable', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });
  const page = createPageInstance(pageConfig, {
    stageWidth: 300,
    stageHeight: 420,
    imageItems: [
      {
        id: 'img_1',
        localPath: '/tmp/large-portrait.jpg',
        contentVersion: 0,
        boxes: [{ id: 'box_tiny', x: 0.2, y: 0.3, width: 0.02, height: 0.03 }],
        activeBoxId: 'box_tiny',
      },
    ],
    selectedImageId: 'img_1',
    currentImage: {
      id: 'img_1',
      localPath: '/tmp/large-portrait.jpg',
      contentVersion: 0,
      boxes: [{ id: 'box_tiny', x: 0.2, y: 0.3, width: 0.02, height: 0.03 }],
      activeBoxId: 'box_tiny',
    },
  });
  page.getImageInfo = async (src) => {
    if (src.includes('rotated')) {
      return { width: 4200, height: 3000 };
    }
    return { width: 3000, height: 4200 };
  };
  page.exportCanvasImage = async () => '/tmp/rotated.jpg';

  await page.rotateCurrentImageClockwise();

  assert.equal(page.data.selectedImageId, 'img_1');
  assert.equal(page.data.currentImage.localPath, '/tmp/rotated.jpg');
  assert.equal(page.data.currentImage.contentVersion, 1);
  assert.equal(page.data.activeBox.id, 'box_tiny');
  assert.equal(page.data.activeBox.width, 0.03);
  assert.equal(page.data.activeBox.height, 0.02);
});

test('removeActiveBox keeps the current image and selects the next neighboring box', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });
  const page = createPageInstance(pageConfig, {
    imageItems: [
      {
        id: 'img_1',
        localPath: '/tmp/source.jpg',
        boxes: [
          { id: 'box_1', x: 0.1, y: 0.1, width: 0.2, height: 0.2 },
          { id: 'box_2', x: 0.35, y: 0.1, width: 0.2, height: 0.2 },
          { id: 'box_3', x: 0.6, y: 0.1, width: 0.2, height: 0.2 },
        ],
        activeBoxId: 'box_2',
      },
    ],
    selectedImageId: 'img_1',
    currentImage: {
      id: 'img_1',
      localPath: '/tmp/source.jpg',
      boxes: [
        { id: 'box_1', x: 0.1, y: 0.1, width: 0.2, height: 0.2 },
        { id: 'box_2', x: 0.35, y: 0.1, width: 0.2, height: 0.2 },
        { id: 'box_3', x: 0.6, y: 0.1, width: 0.2, height: 0.2 },
      ],
      activeBoxId: 'box_2',
    },
    activeBox: { id: 'box_2' },
    imageWidth: 300,
    imageHeight: 420,
  });

  await page.removeActiveBox();

  assert.equal(page.data.selectedImageId, 'img_1');
  assert.deepEqual(page.data.currentImage.boxes.map((box) => box.id), ['box_1', 'box_3']);
  assert.equal(page.data.currentImage.activeBoxId, 'box_3');
  assert.equal(page.data.activeBox.id, 'box_3');
});

test('submitUpload exposes each parent-visible upload stage without real network calls', async () => {
  let statusRefreshCalls = 0;
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => {
      statusRefreshCalls += 1;
      return { task: { id: 9001, status: 'ready' } };
    },
  });
  const page = createPageInstance(pageConfig, createReadyUploadData());
  page.exportBoxCrop = async () => '/tmp/crop.jpg';

  await withWx(async () => {
    await page.submitUpload();
  });

  const stageUpdates = page.__updates
    .filter((item) => Object.prototype.hasOwnProperty.call(item, 'uploadStage'))
    .map((item) => ({
      stage: item.uploadStage,
      text: item.uploadStageText,
    }));

  assert.deepEqual(stageUpdates.map((item) => item.stage), [
    'preparing_crop',
    'uploading_audio',
    'uploading_image',
    'task_accepted',
  ]);
  assert.match(stageUpdates[0].text, /裁切第 1\/1 题/);
  assert.match(stageUpdates[1].text, /语音说明/);
  assert.match(stageUpdates[2].text, /题图/);
  assert.match(stageUpdates[3].text, /已接收/);
  assert.equal(statusRefreshCalls, 0);
  assert.equal(page.data.uploadTaskSummary.state, 'background');
  assert.match(page.data.uploadTaskSummary.description, /可以先离开本页/);
  assert.equal(page.data.submitting, false);
});

test('submitUpload releases the page and shows a specific failed stage after crop export fails', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });
  const page = createPageInstance(pageConfig, createReadyUploadData());
  page.exportBoxCrop = async () => {
    throw new Error('裁切图片失败，请重试');
  };

  await withWx(async () => {
    await page.submitUpload();
  });

  assert.equal(page.data.submitting, false);
  assert.equal(page.data.uploadStage, 'failed');
  assert.match(page.data.uploadStageText, /裁切图片失败，请重试/);
  assert.match(page.data.errorMessage, /裁切图片失败，请重试/);
});

test('submitUpload reports crop export failure by item without clearing the draft', async () => {
  let cropCalls = 0;
  const submittedFiles = [];
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => {
      throw new Error('voice should not upload for text boxes');
    },
    submitParentWrongQuestion: async (_wx, _serverUrl, params) => {
      submittedFiles.push(params.filePath);
      return { task: { id: 9001, status: 'pending' } };
    },
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'processing' } }),
  });
  const page = createPageInstance(pageConfig, createTwoBoxUploadData());
  page.exportBoxCrop = async () => {
    cropCalls += 1;
    if (cropCalls === 2) {
      throw new Error('canvas export timeout');
    }
    return `/tmp/crop-${cropCalls}.jpg`;
  };

  await withWx(async () => {
    await page.submitUpload();
  });

  assert.deepEqual(submittedFiles, ['/tmp/crop-1.jpg']);
  assert.equal(page.data.imageItems.length, 1);
  assert.equal(page.data.selectedImageId, 'img_1');
  assert.equal(page.data.activeBox.id, 'box_2');
  assert.deepEqual(page.data.successTaskIds, [9001]);
  assert.equal(page.data.uploadStage, 'background');
  assert.match(page.data.errorMessage, /第 2\/2 题裁切失败/);
  assert.match(page.data.uploadStageText, /第 2\/2 题裁切失败/);
});

test('onShow exposes topic controls only for primary bindings and merges website suggestions', async () => {
  const suggestionRequests = [];
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchParentBindings: async () => [
      {
        id: 21,
        studentName: 'Alice',
        className: '六年级 1 班',
        classGrade: '六年级',
      },
      {
        id: 22,
        studentName: 'Bob',
        className: '初一 1 班',
        classGrade: '初一',
      },
    ],
    fetchParentTopicCategorySuggestions: async (_wx, _serverUrl, params) => {
      suggestionRequests.push(params);
      return { items: ['周期问题', '几何'] };
    },
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });

  const primaryPage = createPageInstance(pageConfig);
  primaryPage.options = { bindingId: '21' };
  await withWx(async () => {
    await primaryPage.onShow();
  }, {
    getStorageSync() {
      return '';
    },
  });

  assert.equal(primaryPage.data.showPrimaryTopicCategory, true);
  assert.deepEqual(suggestionRequests, [{ openId: 'openid-parent-1', topicCategory: '' }]);
  assert.equal(primaryPage.data.topicCategoryOptions.includes('周期问题'), true);
  assert.equal(primaryPage.data.topicCategoryOptions.at(-1), '自定义');

  const middlePage = createPageInstance(pageConfig);
  middlePage.options = { bindingId: '22' };
  await withWx(async () => {
    await middlePage.onShow();
  }, {
    getStorageSync() {
      return '';
    },
  });

  assert.equal(middlePage.data.showPrimaryTopicCategory, false);
  assert.equal(suggestionRequests.length, 1);
});

test('submitUpload sends unclassified topic for non-primary bindings', async () => {
  const submittedTopics = [];
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => {
      throw new Error('voice should not upload for text boxes');
    },
    submitParentWrongQuestion: async (_wx, _serverUrl, params) => {
      submittedTopics.push(params.topicCategory);
      return { task: { id: 9001, status: 'pending' } };
    },
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });
  const page = createPageInstance(pageConfig, {
    ...createTwoBoxUploadData(),
    binding: {
      id: 22,
      studentName: 'Bob',
      className: '初一 1 班',
      classGrade: '初一',
    },
    showPrimaryTopicCategory: false,
  });
  page.exportBoxCrop = async (_imageItem, box) => `/tmp/${box.id}.jpg`;

  await withWx(async () => {
    await page.submitUpload();
  });

  assert.deepEqual(submittedTopics, ['未分类', '未分类']);
});

test('submitUpload keeps the original draft and allows retry after a retryable upload failure', async () => {
  let submitCalls = 0;
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => {
      throw new Error('voice should not upload for text boxes');
    },
    submitParentWrongQuestion: async () => {
      submitCalls += 1;
      if (submitCalls === 1) {
        const error = new Error('网络连接中断，草稿已保留，请检查网络后重试。');
        error.retryable = true;
        throw error;
      }
      return { task: { id: 9001, status: 'pending' } };
    },
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });
  const originalData = createTwoBoxUploadData();
  const page = createPageInstance(pageConfig, originalData);
  page.exportBoxCrop = async (_imageItem, box) => `/tmp/${box.id}.jpg`;

  await withWx(async () => {
    await page.submitUpload();
  });

  assert.equal(page.data.submitting, false);
  assert.equal(page.data.uploadStage, 'failed');
  assert.match(page.data.uploadStageText, /草稿已保留/);
  assert.equal(page.data.imageItems.length, 1);
  assert.equal(page.data.currentImage.id, 'img_1');
  assert.equal(page.data.activeBox.id, 'box_2');

  await withWx(async () => {
    await page.submitUpload();
  });

  assert.equal(submitCalls, 3);
  assert.deepEqual(page.data.successTaskIds, [9001, 9001]);
  assert.equal(page.data.uploadTaskSummary.state, 'background');
  assert.match(page.data.uploadTaskSummary.description, /可以先离开本页/);
  assert.equal(page.data.imageItems.length, 0);
});

test('exportBoxCrop keeps large landscape crops inside protected dimensions', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });
  const page = createPageInstance(pageConfig, {});
  const exportOptions = [];
  page.getImageInfo = async () => ({ width: 4200, height: 3000 });
  page.exportCanvasImage = async (_filePath, options) => {
    exportOptions.push(options);
    return '/tmp/crop.jpg';
  };

  const croppedPath = await page.exportBoxCrop(
    { id: 'img_landscape', localPath: '/tmp/large-landscape.jpg' },
    { id: 'box_full', x: 0, y: 0, width: 1, height: 1 }
  );

  assert.equal(croppedPath, '/tmp/crop.jpg');
  assert.equal(exportOptions[0].canvasWidth, 1792);
  assert.equal(exportOptions[0].canvasHeight, 1280);
  assert.equal(exportOptions[0].quality, 0.82);
  assert.deepEqual(exportOptions[0].sourceRect, {
    x: 0,
    y: 0,
    width: 4200,
    height: 3000,
  });
});

test('crop export lock blocks gestures and duplicate submit actions', async () => {
  let ensureCalls = 0;
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => {
      ensureCalls += 1;
      return { openId: 'openid-parent-1' };
    },
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });
  const page = createPageInstance(pageConfig, {
    ...createTwoBoxUploadData(),
    cropExporting: true,
    displayBoxes: [
      { id: 'box_2', left: 20, top: 30, width: 120, height: 90, active: true },
    ],
    imageLeft: 0,
    imageTop: 0,
    imageWidth: 300,
    imageHeight: 420,
  });

  page.onBoxTouchStart({
    touches: [{ clientX: 30, clientY: 40 }],
    currentTarget: { dataset: { boxId: 'box_2', mode: 'move' } },
  });
  await page.submitUpload();

  assert.equal(Boolean(page.touchState), false);
  assert.equal(ensureCalls, 0);
  assert.equal(page.data.selectedImageId, 'img_1');
  assert.equal(page.data.activeBox.id, 'box_2');
});

test('pollUploadTasks exposes background processing when tasks remain pending', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async (_wx, _serverUrl, params) => ({
      task: { id: params.taskId, status: 'processing' },
    }),
  });
  const page = createPageInstance(pageConfig, createReadyUploadData());

  await withWx(async () => {
    const summary = await page.pollUploadTasks('openid-parent-1', [9001]);
    assert.equal(summary.state, 'background');
  });

  assert.equal(page.data.uploadStage, 'background');
  assert.match(page.data.uploadStageText, /云端继续识别/);
  assert.match(page.data.uploadStageText, /可以先离开本页/);
});

test('pollUploadTasks exposes partial failure separately from total failure', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async (_wx, _serverUrl, params) => ({
      task: Number(params.taskId) === 9001
        ? { id: 9001, status: 'ready' }
        : { id: 9002, status: 'failed', error_message: '题图太模糊' },
    }),
  });
  const page = createPageInstance(pageConfig, createReadyUploadData());

  await withWx(async () => {
    const summary = await page.pollUploadTasks('openid-parent-1', [9001, 9002]);
    assert.equal(summary.state, 'partial_failed');
  });

  assert.equal(page.data.uploadStage, 'partial_failed');
  assert.match(page.data.uploadStageText, /部分识别失败/);
});

test('pollUploadTasks survives one transient status request failure without losing accepted tasks', async () => {
  let calls = 0;
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async (_wx, _serverUrl, params) => {
      calls += 1;
      if (Number(params.taskId) === 9002 && calls <= 2) {
        throw new Error('status timeout');
      }
      return {
        task: { id: params.taskId, status: 'ready' },
      };
    },
  });
  const page = createPageInstance(pageConfig, createReadyUploadData());
  page.data.successTaskIds = [9001, 9002];

  await withWx(async () => {
    const summary = await page.pollUploadTasks('openid-parent-1', [9001, 9002]);
    assert.equal(summary.state, 'ready');
  });

  assert.deepEqual(page.data.successTaskIds, [9001, 9002]);
  assert.equal(page.data.uploadStage, 'ready');
  assert.equal(page.data.errorMessage, '');
});

test('pollUploadTasks reports mixed ready failed and pending tasks as partial background work after max attempts', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async (_wx, _serverUrl, params) => {
      const taskId = Number(params.taskId);
      if (taskId === 9001) {
        return { task: { id: 9001, status: 'ready' } };
      }
      if (taskId === 9002) {
        return { task: { id: 9002, status: 'failed', error_message: '题图太模糊' } };
      }
      return { task: { id: 9003, status: 'processing' } };
    },
  });
  const page = createPageInstance(pageConfig, createReadyUploadData());
  page.data.successTaskIds = [9001, 9002, 9003];

  await withWx(async () => {
    const summary = await page.pollUploadTasks('openid-parent-1', [9001, 9002, 9003]);
    assert.equal(summary.state, 'partial_failed');
    assert.equal(summary.readyCount, 1);
    assert.equal(summary.failedCount, 1);
    assert.equal(summary.pendingCount, 1);
    assert.match(summary.description, /1 条还在云端继续识别/);
  });

  assert.deepEqual(page.data.successTaskIds, [9001, 9002, 9003]);
  assert.equal(page.data.uploadStage, 'partial_failed');
  assert.match(page.data.uploadStageText, /云端继续识别/);
});

test('pollUploadTasks treats malformed task payloads as pending with the original task id', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { status: 'ready' } }),
  });
  const page = createPageInstance(pageConfig, createReadyUploadData());
  page.data.successTaskIds = [9001];

  await withWx(async () => {
    const summary = await page.pollUploadTasks('openid-parent-1', [9001]);
    assert.equal(summary.state, 'background');
  });

  assert.deepEqual(page.data.successTaskIds, [9001]);
  assert.equal(page.data.uploadStage, 'background');
  assert.match(page.data.uploadStageText, /云端继续识别/);
});

test('restoreAcceptedUploadTasks resumes pending stored tasks without re-uploading cropped images', async () => {
  const requestedTaskIds = [];
  const storedWrites = [];
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => {
      throw new Error('should not submit a recovered task again');
    },
    fetchWrongQuestionUploadTask: async (_wx, _serverUrl, params) => {
      requestedTaskIds.push(Number(params.taskId));
      if (Number(params.taskId) === 9001) {
        return { task: { id: 9001, status: 'processing' } };
      }
      return { task: { id: 9002, status: 'ready' } };
    },
  });
  const page = createPageInstance(pageConfig, {
    binding: {
      id: 21,
      studentName: 'Alice',
      className: '六年级 1 班',
    },
  });
  page.exportBoxCrop = async () => {
    throw new Error('should not export a recovered task again');
  };

  await withWx(async () => {
    const summary = await page.restoreAcceptedUploadTasks('openid-parent-1', page.data.binding);
    assert.equal(summary.state, 'background');
  }, {
    getStorageSync() {
      return {
        version: 1,
        openId: 'openid-parent-1',
        bindingId: 21,
        child: {
          studentName: 'Alice',
          className: '六年级 1 班',
        },
        tasks: [
          {
            id: 9001,
            status: 'pending',
            imageId: 'img_1',
            boxId: 'box_1',
            topicCategory: '计算',
          },
          {
            id: 9002,
            status: 'pending',
            imageId: 'img_2',
            boxId: 'box_2',
            topicCategory: '几何',
          },
        ],
      };
    },
    setStorageSync(_key, value) {
      storedWrites.push(value);
    },
    removeStorageSync() {},
  });

  assert.ok(requestedTaskIds.includes(9001));
  assert.ok(requestedTaskIds.includes(9002));
  assert.deepEqual(page.data.successTaskIds, [9001, 9002]);
  assert.equal(page.data.uploadStage, 'background');
  assert.match(page.data.uploadStageText, /云端继续识别/);
  assert.equal(storedWrites.at(-1).tasks.length, 1);
  assert.equal(storedWrites.at(-1).tasks[0].id, 9001);
  assert.equal(storedWrites.at(-1).child.studentName, 'Alice');
});

test('restoreAcceptedUploadTasks clears recovered tasks after every task reaches a terminal state', async () => {
  const removedKeys = [];
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => {
      throw new Error('should not submit a recovered task again');
    },
    fetchWrongQuestionUploadTask: async (_wx, _serverUrl, params) => {
      if (Number(params.taskId) === 9001) {
        return { task: { id: 9001, status: 'ready' } };
      }
      return { task: { id: 9002, status: 'failed', error_message: '题图太模糊' } };
    },
  });
  const page = createPageInstance(pageConfig, {
    binding: {
      id: 21,
      studentName: 'Alice',
      className: '六年级 1 班',
    },
  });

  await withWx(async () => {
    const summary = await page.restoreAcceptedUploadTasks('openid-parent-1', page.data.binding);
    assert.equal(summary.state, 'partial_failed');
  }, {
    getStorageSync() {
      return {
        version: 1,
        openId: 'openid-parent-1',
        bindingId: 21,
        child: {
          studentName: 'Alice',
          className: '六年级 1 班',
        },
        tasks: [
          { id: 9001, status: 'pending', imageId: 'img_1', boxId: 'box_1' },
          { id: 9002, status: 'pending', imageId: 'img_2', boxId: 'box_2' },
        ],
      };
    },
    setStorageSync() {
      throw new Error('terminal recovered tasks should not be persisted again');
    },
    removeStorageSync(key) {
      removedKeys.push(key);
    },
  });

  assert.deepEqual(page.data.successTaskIds, [9001, 9002]);
  assert.equal(removedKeys.length, 1);
  assert.match(removedKeys[0], /xr_parent_upload_tasks_v1:openid-parent-1:21/);
});

test('restoreAcceptedUploadTasks shows a recoverable message when stored tasks are corrupted', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
  });
  const page = createPageInstance(pageConfig, {
    binding: {
      id: 21,
      studentName: 'Alice',
      className: '六年级 1 班',
    },
  });

  await withWx(async () => {
    const summary = await page.restoreAcceptedUploadTasks('openid-parent-1', page.data.binding);
    assert.equal(summary, null);
  }, {
    getStorageSync() {
      return '{not-valid-json';
    },
  });

  assert.deepEqual(page.data.successTaskIds, []);
  assert.equal(page.data.uploadStage, 'background');
  assert.match(page.data.uploadStageText, /无法读取本机保存的上传进度/);
});

test('openChildWrongbook keeps a clear progress path after upload acceptance', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'processing' } }),
  });
  const page = createPageInstance(pageConfig, {
    binding: {
      id: 21,
      studentId: 101,
      studentName: 'Alice',
      className: '六年级 1 班',
    },
    successTaskIds: [9001, 9002],
  });
  const navigations = [];

  await withWx(async () => {
    page.openChildWrongbook();
  }, {
    navigateTo(payload) {
      navigations.push(payload);
    },
  });

  assert.equal(navigations.length, 1);
  assert.match(navigations[0].url, /^\/pages\/parent-wrongbook\/index\?/);
  assert.match(navigations[0].url, /studentId=101/);
  assert.match(navigations[0].url, /studentName=Alice/);
  assert.match(navigations[0].url, /uploadTaskIds=9001%2C9002/);
});
