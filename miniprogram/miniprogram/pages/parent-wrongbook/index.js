const app = getApp();
const {
  ensureParentSession,
  fetchChildWrongQuestions,
} = require('../../utils/parentApi');

Page({
  data: {
    studentId: 0,
    studentName: '',
    loading: true,
    errorMessage: '',
    items: [],
  },

  onLoad(query) {
    const studentId = Number(query.studentId || 0);
    const studentName = decodeURIComponent(query.studentName || '');
    this.setData({ studentId, studentName });
    wx.setNavigationBarTitle({ title: studentName ? `${studentName}的错题本` : '错题本' });
  },

  async onShow() {
    const { studentId } = this.data;
    if (!studentId) return;

    this.setData({ loading: true, errorMessage: '' });

    try {
      const session = await ensureParentSession(wx, app.globalData.serverUrl);
      const payload = await fetchChildWrongQuestions(wx, app.globalData.serverUrl, {
        openId: session.openId,
        studentId,
      });
      const items = (payload.items || []).map(normalizeItem);
      this.setData({ items });
    } catch (error) {
      this.setData({
        errorMessage: error instanceof Error ? error.message : '加载失败',
      });
    } finally {
      this.setData({ loading: false });
    }
  },
});

function normalizeItem(item) {
  const raw = item && typeof item === 'object' ? item : {};
  const createdAt = String(raw.created_at || '');
  const dateStr = createdAt ? createdAt.slice(0, 10) : '';
  const analysis = raw.analysis && typeof raw.analysis === 'object' ? raw.analysis : {};
  return {
    id: String(raw.id || ''),
    imageUrl: String(raw.image_url || ''),
    errorType: String(analysis.selected_error_type || raw.primary_error_type || ''),
    errorSummary: String(analysis.student_note || raw.secondary_error_summary || ''),
    isMastered: raw.is_mastered === true || raw.archive_status === 'archived',
    dateStr,
  };
}
