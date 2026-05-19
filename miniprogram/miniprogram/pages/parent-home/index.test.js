const assert = require('node:assert/strict');
const test = require('node:test');

function loadHomePage(parentApi, appGlobalData) {
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
      ...appGlobalData,
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

function createPageInstance(pageConfig) {
  const page = {
    ...pageConfig,
    data: {
      ...JSON.parse(JSON.stringify(pageConfig.data)),
    },
    setData(nextData, callback) {
      this.data = {
        ...this.data,
        ...nextData,
      };
      if (typeof callback === 'function') {
        callback();
      }
    },
  };
  return page;
}

function withWx(testBody) {
  const originalWx = global.wx;
  const calls = [];
  global.wx = {
    navigateTo(options) {
      calls.push({ type: 'navigateTo', options });
    },
  };

  return Promise.resolve()
    .then(() => testBody(calls))
    .finally(() => {
      global.wx = originalWx;
    });
}

const oneBinding = {
  id: 21,
  studentId: 101,
  studentName: 'Alice',
  className: '六年级 1 班',
  teacherName: 'Kayn',
};

test('onShow auto-selects the only child as the current upload child', async () => {
  let storedBindingId = 0;
  const parentApi = {
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchParentBindings: async () => [oneBinding],
    getCurrentParentBindingId: () => storedBindingId,
    setCurrentParentBindingId: (_wx, bindingId) => {
      storedBindingId = Number(bindingId) || 0;
    },
  };
  const pageConfig = loadHomePage(parentApi);
  const page = createPageInstance(pageConfig);

  await withWx(async () => {
    await page.onShow();
  });

  assert.equal(page.data.currentBindingId, 21);
  assert.equal(storedBindingId, 21);
});

test('setCurrentBinding stores the selected child without leaving the my tab', async () => {
  let storedBindingId = 0;
  const parentApi = {
    ensureParentSession: async () => ({ openId: 'openid-parent-1' }),
    fetchParentBindings: async () => [oneBinding, { ...oneBinding, id: 22, studentId: 102, studentName: 'Bob' }],
    getCurrentParentBindingId: () => storedBindingId,
    setCurrentParentBindingId: (_wx, bindingId) => {
      storedBindingId = Number(bindingId) || 0;
    },
  };
  const pageConfig = loadHomePage(parentApi);
  const page = createPageInstance(pageConfig);

  await withWx(async (calls) => {
    await page.onShow();
    page.setCurrentBinding({ currentTarget: { dataset: { bindingId: '22' } } });
    assert.deepEqual(calls, []);
  });

  assert.equal(page.data.currentBindingId, 22);
  assert.equal(storedBindingId, 22);
});
