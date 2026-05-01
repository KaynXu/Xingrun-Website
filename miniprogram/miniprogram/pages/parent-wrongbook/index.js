const app = getApp();
const {
  ensureParentSession,
  fetchChildWrongQuestionLibrary,
  fetchChildWrongQuestions,
  updateChildWrongQuestionTopicCategory,
} = require('../../utils/parentApi');
const { normalizeWrongQuestionLatexPreviewText } = require('./latex-preview');

const TOPIC_CATEGORY_OPTIONS = ['未分类', '计算', '经济', '浓度', '工程', '行程', '几何', '数论', '自定义'];

Page({
  data: {
    studentId: 0,
    studentName: '',
    loading: true,
    errorMessage: '',
    items: [],
    libraryPdfUrl: '',
    openingPdf: false,
    topicCategoryOptions: TOPIC_CATEGORY_OPTIONS,
    topicSummaries: [],
    activeTopicCategory: '全部',
    displayedItems: [],
    editingTopicRecordId: '',
    editingTopicCategory: '',
    savingTopic: false,
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
        topicSummaries: buildTopicSummaries(items),
        displayedItems: filterItemsByTopic(items, this.data.activeTopicCategory),
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

  selectTopicFilter(event) {
    const topicCategory = String((event.currentTarget && event.currentTarget.dataset && event.currentTarget.dataset.topic) || '全部');
    this.setData({
      activeTopicCategory: topicCategory,
      displayedItems: filterItemsByTopic(this.data.items, topicCategory),
    });
  },

  startEditTopicCategory(event) {
    const recordId = String((event.currentTarget && event.currentTarget.dataset && event.currentTarget.dataset.recordId) || '');
    const matched = (this.data.items || []).find((item) => item.id === recordId);
    if (!matched) {
      return;
    }
    this.setData({
      editingTopicRecordId: recordId,
      editingTopicCategory: matched.topicCategory || '未分类',
    });
  },

  cancelEditTopicCategory() {
    this.setData({
      editingTopicRecordId: '',
      editingTopicCategory: '',
    });
  },

  handleTopicCategoryChange(event) {
    const index = Number(event && event.detail ? event.detail.value : 0);
    const nextTopic = TOPIC_CATEGORY_OPTIONS[index] || '未分类';
    this.setData({
      editingTopicCategory: nextTopic === '自定义' ? '' : nextTopic,
    });
  },

  handleCustomTopicInput(event) {
    this.setData({
      editingTopicCategory: String(event && event.detail ? event.detail.value : '').trim(),
    });
  },

  async saveTopicCategory() {
    const recordId = String(this.data.editingTopicRecordId || '').trim();
    const topicCategory = String(this.data.editingTopicCategory || '未分类').trim() || '未分类';
    if (!recordId || this.data.savingTopic) {
      return;
    }
    this.setData({ savingTopic: true });
    try {
      const session = await ensureParentSession(wx, app.globalData.serverUrl);
      await updateChildWrongQuestionTopicCategory(wx, app.globalData.serverUrl, {
        openId: session.openId,
        recordId,
        topicCategory,
      });
      const items = (this.data.items || []).map((item) => {
        if (item.id !== recordId) {
          return item;
        }
        return {
          ...item,
          topicCategory,
        };
      });
      this.setData({
        items,
        topicSummaries: buildTopicSummaries(items),
        displayedItems: filterItemsByTopic(items, this.data.activeTopicCategory),
        editingTopicRecordId: '',
        editingTopicCategory: '',
      });
      wx.showToast({ title: '已更新分类', icon: 'success' });
    } catch (error) {
      wx.showToast({
        title: error instanceof Error ? error.message : '分类更新失败',
        icon: 'none',
      });
    } finally {
      this.setData({ savingTopic: false });
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
    questionPreviewText: normalizeWrongQuestionLatexPreviewText(String(raw.question_text || '').trim()),
    errorType: String(analysis.selected_error_type || raw.primary_error_type || ''),
    errorSummary: String(analysis.student_note || raw.secondary_error_summary || ''),
    topicCategory: normalizeTopicCategory(String(raw.topic_category || raw.topicCategory || analysis.topic_category || analysis.topicCategory || '')),
    isMastered: raw.is_mastered === true || raw.archive_status === 'archived',
    dateStr,
  };
}

function normalizeTopicCategory(value) {
  const normalized = String(value || '').trim();
  return normalized || '未分类';
}

function buildTopicSummaries(items) {
  const counts = {};
  (items || []).forEach((item) => {
    const topicCategory = normalizeTopicCategory(item.topicCategory);
    counts[topicCategory] = (counts[topicCategory] || 0) + 1;
  });
  const topicItems = Object.keys(counts).sort((left, right) => {
    if (left === '未分类') return -1;
    if (right === '未分类') return 1;
    return left.localeCompare(right, 'zh-Hans-CN');
  }).map((topicCategory) => {
    return {
      topicCategory,
      count: counts[topicCategory],
    };
  });
  return [{ topicCategory: '全部', count: (items || []).length }].concat(topicItems);
}

function filterItemsByTopic(items, topicCategory) {
  const normalizedTopic = normalizeTopicCategory(topicCategory);
  if (normalizedTopic === '全部') {
    return items || [];
  }
  return (items || []).filter((item) => normalizeTopicCategory(item.topicCategory) === normalizedTopic);
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
