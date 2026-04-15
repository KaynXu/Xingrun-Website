const app = getApp();
const {
  ensureParentSession,
  fetchChildWrongQuestionLibrary,
  fetchChildWrongQuestions,
} = require('../../utils/parentApi');

Page({
  data: {
    studentId: 0,
    studentName: '',
    loading: true,
    errorMessage: '',
    items: [],
    libraryPdfUrl: '',
    openingPdf: false,
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
      const libraryPayload = await fetchChildWrongQuestionLibrary(wx, app.globalData.serverUrl, {
        openId: session.openId,
        studentId,
      }).catch(() => null);
      const items = (payload.items || []).map(normalizeItem);
      this.setData({
        items,
        libraryPdfUrl: normalizeLibraryPdfUrl(app.globalData.serverUrl, libraryPayload),
      });
    } catch (error) {
      this.setData({
        errorMessage: error instanceof Error ? error.message : '加载失败',
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  async openWrongQuestionLibraryPdf() {
    const pdfUrl = String(this.data.libraryPdfUrl || '').trim();
    if (!pdfUrl || this.data.openingPdf) {
      return;
    }

    this.setData({ openingPdf: true });
    try {
      const response = await downloadFile(pdfUrl);
      const filePath = String(response.tempFilePath || '').trim();
      if (!filePath) {
        throw new Error('PDF 下载失败，请稍后再试');
      }
      await openDocument(filePath);
    } catch (error) {
      wx.showToast({
        title: error instanceof Error ? error.message : 'PDF 打开失败',
        icon: 'none',
      });
    } finally {
      this.setData({ openingPdf: false });
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
    questionText: String(raw.question_text || '').trim(),
    errorType: String(analysis.selected_error_type || raw.primary_error_type || ''),
    errorSummary: String(analysis.student_note || raw.secondary_error_summary || ''),
    isMastered: raw.is_mastered === true || raw.archive_status === 'archived',
    dateStr,
  };
}

function normalizeLibraryPdfUrl(serverUrl, payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const totalItems = Number(source.total_items || 0) || 0;
  const pdfUrl = String(source.pdf_url || '').trim();
  if (!pdfUrl || totalItems <= 0) {
    return '';
  }
  if (/^https?:\/\//i.test(pdfUrl)) {
    return pdfUrl;
  }
  return `${String(serverUrl || '').replace(/\/+$/, '')}${pdfUrl.startsWith('/') ? pdfUrl : `/${pdfUrl}`}`;
}

function downloadFile(url) {
  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url,
      success: (response) => {
        if (Number(response.statusCode || 0) >= 200 && Number(response.statusCode || 0) < 300) {
          resolve(response);
          return;
        }
        reject(new Error('PDF 下载失败，请稍后再试'));
      },
      fail: (error) => {
        reject(new Error((error && error.errMsg) || 'PDF 下载失败，请稍后再试'));
      },
    });
  });
}

function openDocument(filePath) {
  return new Promise((resolve, reject) => {
    wx.openDocument({
      filePath,
      showMenu: true,
      success: resolve,
      fail: (error) => {
        reject(new Error((error && error.errMsg) || 'PDF 打开失败'));
      },
    });
  });
}
