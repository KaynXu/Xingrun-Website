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

function withWx(testBody) {
  const originalWx = global.wx;
  const toasts = [];
  global.wx = {
    showToast(payload) {
      toasts.push(payload);
    },
  };
  return Promise.resolve()
    .then(() => testBody(toasts))
    .finally(() => {
      global.wx = originalWx;
    });
}

test('submitUpload exposes each parent-visible upload stage without real network calls', async () => {
  const pageConfig = loadUploadPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    uploadParentReasonAudio: async () => ({ audioUrl: 'https://example.com/files/reason.mp3' }),
    submitParentWrongQuestion: async () => ({ task: { id: 9001, status: 'pending' } }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: 9001, status: 'ready' } }),
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
    'recognizing',
    'ready',
  ]);
  assert.match(stageUpdates[0].text, /裁切第 1\/1 题/);
  assert.match(stageUpdates[1].text, /语音说明/);
  assert.match(stageUpdates[2].text, /题图/);
  assert.match(stageUpdates[3].text, /已接收/);
  assert.match(stageUpdates[4].text, /服务器正在识别/);
  assert.match(stageUpdates[5].text, /错题本已更新/);
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
  assert.match(page.data.uploadStageText, /后台继续识别/);
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
