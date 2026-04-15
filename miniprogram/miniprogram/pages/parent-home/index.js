const app = getApp();
const {
  ensureParentSession,
  fetchParentBindings,
} = require('../../utils/parentApi');

Page({
  data: {
    loading: true,
    errorMessage: '',
    bindings: [],
  },

  async onShow() {
    this.setData({
      loading: true,
      errorMessage: '',
    });

    try {
      const session = await ensureParentSession(wx, app.globalData.serverUrl);
      app.globalData.parentSession = session;
      const bindings = await fetchParentBindings(wx, app.globalData.serverUrl, {
        openId: session.openId,
      });
      app.globalData.parentBindings = bindings;
      this.setData({
        bindings,
      });
    } catch (error) {
      this.setData({
        errorMessage: error instanceof Error ? error.message : '家长登录失败',
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  goBindMore() {
    wx.navigateTo({ url: '/pages/parent-bind/index' });
  },

  goUpload(event) {
    const bindingId = Number(event.currentTarget.dataset.bindingId || 0);
    if (!bindingId) {
      return;
    }

    wx.navigateTo({
      url: `/pages/parent-upload/index?bindingId=${bindingId}`,
    });
  },

  goWrongbook(event) {
    const studentId = Number(event.currentTarget.dataset.studentId || 0);
    const studentName = String(event.currentTarget.dataset.studentName || '');
    if (!studentId) {
      return;
    }

    wx.navigateTo({
      url: `/pages/parent-wrongbook/index?studentId=${studentId}&studentName=${encodeURIComponent(studentName)}`,
    });
  },
});
