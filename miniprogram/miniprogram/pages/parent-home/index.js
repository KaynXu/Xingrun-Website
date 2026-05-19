const app = getApp();
const {
  ensureParentSession,
  fetchParentBindings,
  getCurrentParentBindingId,
  setCurrentParentBindingId,
} = require('../../utils/parentApi');

Page({
  data: {
    loading: true,
    errorMessage: '',
    bindings: [],
    currentBindingId: 0,
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
      const storedBindingId = getCurrentParentBindingId(wx);
      const hasStoredBinding = bindings.some((item) => item.id === storedBindingId);
      const currentBindingId = hasStoredBinding
        ? storedBindingId
        : bindings.length === 1
          ? bindings[0].id
          : 0;
      if (currentBindingId && currentBindingId !== storedBindingId) {
        setCurrentParentBindingId(wx, currentBindingId);
      }
      app.globalData.parentBindings = bindings;
      app.globalData.currentParentBindingId = currentBindingId;
      this.setData({
        bindings,
        currentBindingId,
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

  setCurrentBinding(event) {
    const bindingId = Number(event.currentTarget.dataset.bindingId || 0);
    if (!bindingId) {
      return;
    }
    setCurrentParentBindingId(wx, bindingId);
    app.globalData.currentParentBindingId = bindingId;
    this.setData({ currentBindingId: bindingId });
  },

  goWrongbook(event) {
    const studentId = Number(event.currentTarget.dataset.studentId || 0);
    const studentName = String(event.currentTarget.dataset.studentName || '');
    const className = String(event.currentTarget.dataset.className || '');
    const classGrade = String(event.currentTarget.dataset.classGrade || '');
    if (!studentId) {
      return;
    }

    const query = [`studentId=${studentId}`, `studentName=${encodeURIComponent(studentName)}`];
    if (className) {
      query.push(`className=${encodeURIComponent(className)}`);
    }
    if (classGrade) {
      query.push(`classGrade=${encodeURIComponent(classGrade)}`);
    }
    wx.navigateTo({
      url: `/pages/parent-wrongbook/index?${query.join('&')}`,
    });
  },
});
