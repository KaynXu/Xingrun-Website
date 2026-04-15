const app = getApp();
const {
  bindParentStudent,
  ensureParentSession,
  fetchParentBindings,
  getParentBindings,
  previewClassInvite,
} = require('../../utils/parentApi');

Page({
  data: {
    inviteCode: '',
    loading: false,
    ensuringSession: false,
    errorMessage: '',
    preview: null,
    existingBindings: [],
    savingStudentId: 0,
  },

  onShow() {
    this.refreshBindings();
    this.ensureSessionAndBindings();
  },

  refreshBindings() {
    const existingBindings = getParentBindings(wx);
    app.globalData.parentBindings = existingBindings;
    this.setData({ existingBindings });
  },

  async ensureSessionAndBindings() {
    if (this.data.ensuringSession) {
      return;
    }

    this.setData({ ensuringSession: true, errorMessage: '' });
    try {
      const session = await ensureParentSession(wx, app.globalData.serverUrl);
      app.globalData.parentSession = session;
      const existingBindings = await fetchParentBindings(wx, app.globalData.serverUrl, {
        openId: session.openId,
      });
      app.globalData.parentBindings = existingBindings;
      this.setData({ existingBindings });
    } catch (error) {
      this.setData({
        errorMessage: error instanceof Error ? error.message : '家长登录失败',
      });
    } finally {
      this.setData({ ensuringSession: false });
    }
  },

  handleInviteInput(event) {
    this.setData({
      inviteCode: event.detail.value,
    });
  },

  async previewInvite() {
    const inviteCode = String(this.data.inviteCode || '').trim().toUpperCase();
    if (!inviteCode) {
      wx.showToast({ title: '请先输入邀请码', icon: 'none' });
      return;
    }

    this.setData({
      loading: true,
      errorMessage: '',
      preview: null,
    });

    try {
      const session = await ensureParentSession(wx, app.globalData.serverUrl);
      app.globalData.parentSession = session;
      const preview = await previewClassInvite(wx, app.globalData.serverUrl, {
        openId: session.openId,
        inviteCode,
      });
      this.setData({ preview });
    } catch (error) {
      this.setData({
        errorMessage: error instanceof Error ? error.message : '班级预览失败',
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  async bindStudent(event) {
    const studentId = Number(event.currentTarget.dataset.studentId || 0);
    const studentName = String(event.currentTarget.dataset.studentName || '').trim();
    const preview = this.data.preview || {};
    const classId = Number(preview.class_id || 0);
    const className = String(preview.class_name || '').trim();
    const session = app.globalData.parentSession;

    if (!session || !session.openId || !classId || !studentId) {
      wx.showToast({ title: '绑定信息不完整', icon: 'none' });
      return;
    }

    this.setData({
      savingStudentId: studentId,
      errorMessage: '',
    });

    try {
      await bindParentStudent(wx, app.globalData.serverUrl, {
        openId: session.openId,
        classId,
        className,
        studentId,
        studentName,
        teacherName: '',
      });
      const existingBindings = getParentBindings(wx);
      app.globalData.parentBindings = existingBindings;
      this.setData({ existingBindings });
      wx.showToast({ title: '绑定成功', icon: 'success' });
      setTimeout(() => {
        wx.reLaunch({ url: '/pages/parent-home/index' });
      }, 250);
    } catch (error) {
      this.setData({
        errorMessage: error instanceof Error ? error.message : '绑定学生失败',
      });
    } finally {
      this.setData({ savingStudentId: 0 });
    }
  },

  goHome() {
    wx.reLaunch({ url: '/pages/parent-home/index' });
  },
});
