const assert = require('node:assert/strict');
const test = require('node:test');

function loadWrongbookPage(parentApi) {
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
  return page;
}

function withWx(testBody, wxOverrides) {
  const originalWx = global.wx;
  const toasts = [];
  global.wx = {
    setNavigationBarTitle() {},
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

test('onShow refreshes ready upload task status before loading parent wrongbook and PDF state', async () => {
  let taskStatusFetched = false;
  let wrongQuestionsFetchedAfterTaskStatus = false;
  const pageConfig = loadWrongbookPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchWrongQuestionUploadTask: async (_wx, _serverUrl, params) => {
      assert.equal(params.taskId, '9001');
      taskStatusFetched = true;
      return { task: { id: '9001', status: 'ready' } };
    },
    fetchChildWrongQuestions: async () => {
      wrongQuestionsFetchedAfterTaskStatus = taskStatusFetched;
      return {
        items: [
          {
            id: 'record-1',
            image_url: 'https://files.example.com/record.png',
            question_text: '计算 $2+3\\times4$ 的结果。',
            recognition_status: 'recognized',
            created_at: '2026-05-03 10:00:00',
            analysis: {
              selected_error_type: '计算问题',
              student_note: '乘法优先级漏掉了',
            },
          },
        ],
      };
    },
    fetchChildWrongQuestionLibrary: async () => ({
      total_items: 1,
      pdf_url: '/api/wechat/student-libraries/101',
    }),
    updateChildWrongQuestionTopicCategory: async () => ({ ok: true }),
  });
  const page = createPageInstance(pageConfig);

  await withWx(async () => {
    page.onLoad({
      studentId: '101',
      studentName: encodeURIComponent('Alice'),
      uploadTaskIds: '9001',
    });
    await page.onShow();
  });

  assert.equal(wrongQuestionsFetchedAfterTaskStatus, true);
  assert.equal(page.data.uploadTaskSummary.state, 'ready');
  assert.match(page.data.uploadStatusText, /已加入错题本/);
  assert.equal(page.data.displayedItems.length, 1);
  assert.match(page.data.displayedItems[0].questionPreviewText, /2\+3/);
  assert.equal(page.data.libraryPdfReady, true);
  assert.equal(page.data.libraryPdfUrl, 'https://example.com/api/wechat/student-libraries/101');
});

test('onShow reports failed upload tasks and marks failed wrongbook cards without AI success copy', async () => {
  const pageConfig = loadWrongbookPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchWrongQuestionUploadTask: async () => ({
      task: {
        id: '9002',
        status: 'failed',
        parent_error_message: '错题处理失败，原图已保留，老师稍后可查看。',
      },
    }),
    fetchChildWrongQuestions: async () => ({
      items: [
        {
          id: 'record-failed',
          image_url: 'https://files.example.com/failed.png',
          question_text: '这段 AI 文本不应该展示',
          recognition_status: 'failed',
          recognition_error: '题图太模糊',
          created_at: '2026-05-03 10:05:00',
        },
      ],
    }),
    fetchChildWrongQuestionLibrary: async () => ({
      total_items: 0,
      pdf_url: '',
    }),
    updateChildWrongQuestionTopicCategory: async () => ({ ok: true }),
  });
  const page = createPageInstance(pageConfig);

  await withWx(async () => {
    page.onLoad({
      studentId: '101',
      studentName: 'Alice',
      uploadTaskIds: '9002',
    });
    await page.onShow();
  });

  assert.equal(page.data.uploadTaskSummary.state, 'failed');
  assert.match(page.data.uploadStatusText, /错题处理失败，原图已保留/);
  assert.equal(page.data.displayedItems[0].questionPreviewText, '');
  assert.match(page.data.displayedItems[0].recognitionStatusText, /识别失败/);
  assert.match(page.data.displayedItems[0].recognitionStatusText, /题图太模糊/);
});

test('onShow keeps background-processing uploads visible and explains PDF is not ready yet', async () => {
  const pageConfig = loadWrongbookPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchWrongQuestionUploadTask: async () => ({
      task: { id: '9003', status: 'processing' },
    }),
    fetchChildWrongQuestions: async () => ({ items: [] }),
    fetchChildWrongQuestionLibrary: async () => ({
      total_items: 0,
      pdf_url: '',
    }),
    updateChildWrongQuestionTopicCategory: async () => ({ ok: true }),
  });
  const page = createPageInstance(pageConfig);

  await withWx(async () => {
    page.onLoad({
      studentId: '101',
      studentName: 'Alice',
      uploadTaskIds: '9003',
    });
    await page.onShow();
  });

  assert.equal(page.data.uploadTaskSummary.state, 'background');
  assert.match(page.data.uploadStatusText, /(?:后台|云端).*识别/);
  assert.equal(page.data.libraryPdfReady, false);
  assert.match(page.data.libraryPdfStatusText, /识别完成后/);
});

test('onShow surfaces missing pdf_url as a recoverable PDF state', async () => {
  const pageConfig = loadWrongbookPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: '9001', status: 'ready' } }),
    fetchChildWrongQuestions: async () => ({
      items: [
        {
          id: 'record-1',
          image_url: 'https://files.example.com/record.png',
          question_text: '计算 1+1。',
          recognition_status: 'recognized',
          created_at: '2026-05-03 10:00:00',
        },
      ],
    }),
    fetchChildWrongQuestionLibrary: async () => ({
      total_items: 1,
      pdf_url: '',
    }),
    updateChildWrongQuestionTopicCategory: async () => ({ ok: true }),
  });
  const page = createPageInstance(pageConfig);

  await withWx(async () => {
    page.onLoad({
      studentId: '101',
      studentName: 'Alice',
    });
    await page.onShow();
  });

  assert.equal(page.data.libraryPdfReady, false);
  assert.equal(page.data.libraryPdfUrl, '');
  assert.match(page.data.libraryPdfStatusText, /PDF 暂时不可用/);
});

test('onLoad and onShow keep topic controls primary-only', async () => {
  const pageConfig = loadWrongbookPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: '9001', status: 'ready' } }),
    fetchChildWrongQuestions: async () => ({
      items: [
        {
          id: 'record-1',
          image_url: 'https://files.example.com/record.png',
          question_text: '计算 1+1。',
          recognition_status: 'recognized',
          topic_category: '周期问题',
          created_at: '2026-05-03 10:00:00',
        },
      ],
    }),
    fetchChildWrongQuestionLibrary: async () => ({
      total_items: 1,
      pdf_url: '',
    }),
    updateChildWrongQuestionTopicCategory: async () => {
      throw new Error('middle-school topic edits should be hidden');
    },
  });

  const middlePage = createPageInstance(pageConfig);
  await withWx(async () => {
    middlePage.onLoad({
      studentId: '101',
      studentName: 'Bob',
      className: encodeURIComponent('初一 1 班'),
      classGrade: encodeURIComponent('初一'),
    });
    await middlePage.onShow();
  });

  assert.equal(middlePage.data.showPrimaryTopicCategory, false);
  assert.deepEqual(middlePage.data.topicSummaries, []);
  assert.equal(middlePage.data.displayedItems.length, 1);

  const primaryPage = createPageInstance(pageConfig);
  await withWx(async () => {
    primaryPage.onLoad({
      studentId: '102',
      studentName: 'Alice',
      className: encodeURIComponent('六年级 1 班'),
      classGrade: encodeURIComponent('六年级'),
    });
    await primaryPage.onShow();
  });

  assert.equal(primaryPage.data.showPrimaryTopicCategory, true);
  assert.equal(primaryPage.data.topicSummaries.some((item) => item.topicCategory === '周期问题'), true);
});

test('saveTopicCategory ignores non-primary pages', async () => {
  let updateCalled = false;
  const pageConfig = loadWrongbookPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: '9001', status: 'ready' } }),
    fetchChildWrongQuestions: async () => ({ items: [] }),
    fetchChildWrongQuestionLibrary: async () => ({ total_items: 0, pdf_url: '' }),
    updateChildWrongQuestionTopicCategory: async () => {
      updateCalled = true;
      return { ok: true };
    },
  });
  const page = createPageInstance(pageConfig, {
    showPrimaryTopicCategory: false,
    editingTopicRecordId: 'record-1',
    editingTopicCategory: '周期问题',
  });

  await withWx(async () => {
    await page.saveTopicCategory();
  });

  assert.equal(updateCalled, false);
  assert.equal(page.data.savingTopic, false);
});

test('openWrongQuestionLibraryPdf shows recovery messages for not-ready, download, and open failures', async () => {
  const pageConfig = loadWrongbookPage({
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchWrongQuestionUploadTask: async () => ({ task: { id: '9001', status: 'ready' } }),
    fetchChildWrongQuestions: async () => ({ items: [] }),
    fetchChildWrongQuestionLibrary: async () => ({ total_items: 0, pdf_url: '' }),
    updateChildWrongQuestionTopicCategory: async () => ({ ok: true }),
  });

  const notReadyPage = createPageInstance(pageConfig, {
    libraryPdfUrl: '',
    libraryPdfStatusText: 'PDF 会在识别完成后生成，请稍后刷新。',
  });
  await withWx(async (toasts) => {
    await notReadyPage.openWrongQuestionLibraryPdf();
    assert.equal(toasts[0].title, 'PDF 会在识别完成后生成，请稍后刷新。');
  });

  const downloadFailPage = createPageInstance(pageConfig, {
    libraryPdfUrl: 'https://example.com/api/wechat/student-libraries/101',
    libraryPdfReady: true,
  });
  await withWx(async (toasts) => {
    await downloadFailPage.openWrongQuestionLibraryPdf();
    assert.match(toasts[0].title, /PDF 下载失败/);
  }, {
    downloadFile(payload) {
      payload.fail({ errMsg: 'network fail' });
    },
  });

  const openFailPage = createPageInstance(pageConfig, {
    libraryPdfUrl: 'https://example.com/api/wechat/student-libraries/101',
    libraryPdfReady: true,
  });
  await withWx(async (toasts) => {
    await openFailPage.openWrongQuestionLibraryPdf();
    assert.match(toasts[0].title, /PDF 打开失败/);
  }, {
    downloadFile(payload) {
      payload.success({ statusCode: 200, tempFilePath: '/tmp/student.pdf' });
    },
    openDocument(payload) {
      payload.fail({ errMsg: 'openDocument fail' });
    },
  });
});
