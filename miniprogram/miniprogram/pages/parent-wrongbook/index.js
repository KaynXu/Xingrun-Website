const app = getApp();
const {
  ensureParentSession,
  fetchChildWrongQuestionLibrary,
  fetchChildWrongQuestions,
  fetchWrongQuestionUploadTask,
  updateChildWrongQuestionTopicCategory,
} = require('../../utils/parentApi');
const { isPrimarySchoolBinding } = require('../../utils/classScope');
const { buildUploadTaskSummary } = require('../parent-upload/model');
const { normalizeWrongQuestionLatexPreviewText } = require('./latex-preview');

const TOPIC_CATEGORY_OPTIONS = ['未分类', '计算', '经济', '浓度', '工程', '行程', '几何', '数论', '自定义'];

Page({
  data: {
    studentId: 0,
    studentName: '',
    className: '',
    classGrade: '',
    showPrimaryTopicCategory: false,
    loading: true,
    errorMessage: '',
    items: [],
    uploadTaskIds: [],
    uploadTaskSummary: null,
    uploadStatusText: '',
    libraryPdfUrl: '',
    libraryPdfReady: false,
    libraryPdfStatusText: '',
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
    const className = decodeURIComponent(query.className || '');
    const classGrade = decodeURIComponent(query.classGrade || '');
    const uploadTaskIds = parseUploadTaskIds(query.uploadTaskIds);
    const showPrimaryTopicCategory = isPrimarySchoolBinding({ className, classGrade });
    this.setData({
      studentId,
      studentName,
      className,
      classGrade,
      showPrimaryTopicCategory,
      uploadTaskIds,
      activeTopicCategory: '全部',
    });
    wx.setNavigationBarTitle({ title: studentName ? `${studentName}的错题本` : '错题本' });
  },

  async onShow() {
    const { studentId } = this.data;
    if (!studentId) return;

    this.setData({ loading: true, errorMessage: '' });

    try {
      const session = await ensureParentSession(wx, app.globalData.serverUrl);
      const uploadTaskSummary = await this.refreshUploadTaskSummary(session.openId);
      const payload = await fetchChildWrongQuestions(wx, app.globalData.serverUrl, {
        openId: session.openId,
        studentId,
      });
      const libraryPayload = await fetchChildWrongQuestionLibrary(wx, app.globalData.serverUrl, {
        openId: session.openId,
        studentId,
      }).catch(() => ({ loadError: true }));
      const items = (payload.items || []).map(normalizeItem);
      const showPrimaryTopicCategory = this.data.showPrimaryTopicCategory;
      const pdfState = normalizeLibraryPdfState(app.globalData.serverUrl, libraryPayload, uploadTaskSummary, items.length);
      this.setData({
        items,
        topicSummaries: showPrimaryTopicCategory ? buildTopicSummaries(items) : [],
        displayedItems: showPrimaryTopicCategory ? filterItemsByTopic(items, this.data.activeTopicCategory) : items,
        libraryPdfUrl: pdfState.url,
        libraryPdfReady: pdfState.ready,
        libraryPdfStatusText: pdfState.statusText,
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
    if (this.data.openingPdf) {
      return;
    }
    if (!pdfUrl) {
      wx.showToast({
        title: this.data.libraryPdfStatusText || 'PDF 暂时不可用，请稍后刷新。',
        icon: 'none',
      });
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

  async refreshUploadTaskSummary(openId) {
    const ids = this.data.uploadTaskIds || [];
    if (!ids.length) {
      this.setData({
        uploadTaskSummary: null,
        uploadStatusText: '',
      });
      return null;
    }

    const tasks = await Promise.all(ids.map(async (taskId) => {
      try {
        const payload = await fetchWrongQuestionUploadTask(wx, app.globalData.serverUrl, {
          openId,
          taskId,
        });
        return normalizeUploadTask(taskId, payload && payload.task);
      } catch (_error) {
        return { id: taskId, status: 'processing' };
      }
    }));
    const hasPendingTask = tasks.some((task) => {
      const status = String((task && task.status) || '').trim();
      return status !== 'ready' && status !== 'failed';
    });
    const summary = buildUploadTaskSummary(tasks, hasPendingTask ? { background: true } : undefined);
    this.setData({
      uploadTaskSummary: summary,
      uploadStatusText: summary.description || '',
    });
    return summary;
  },

  selectTopicFilter(event) {
    if (!this.data.showPrimaryTopicCategory) {
      return;
    }
    const topicCategory = String((event.currentTarget && event.currentTarget.dataset && event.currentTarget.dataset.topic) || '全部');
    this.setData({
      activeTopicCategory: topicCategory,
      displayedItems: filterItemsByTopic(this.data.items, topicCategory),
    });
  },

  startEditTopicCategory(event) {
    if (!this.data.showPrimaryTopicCategory) {
      return;
    }
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
    if (!this.data.showPrimaryTopicCategory) {
      return;
    }
    const index = Number(event && event.detail ? event.detail.value : 0);
    const nextTopic = TOPIC_CATEGORY_OPTIONS[index] || '未分类';
    this.setData({
      editingTopicCategory: nextTopic === '自定义' ? '' : nextTopic,
    });
  },

  handleCustomTopicInput(event) {
    if (!this.data.showPrimaryTopicCategory) {
      return;
    }
    this.setData({
      editingTopicCategory: String(event && event.detail ? event.detail.value : '').trim(),
    });
  },

  async saveTopicCategory() {
    if (!this.data.showPrimaryTopicCategory) {
      this.setData({ savingTopic: false });
      return;
    }
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
  const recognitionStatus = normalizeRecognitionStatus(raw);
  return {
    id: String(raw.id || ''),
    imageUrl: String(raw.image_url || ''),
    questionPreviewText: recognitionStatus === 'recognized'
      ? normalizeWrongQuestionLatexPreviewText(String(raw.question_text || '').trim())
      : '',
    errorType: String(analysis.selected_error_type || raw.primary_error_type || ''),
    errorSummary: String(analysis.student_note || raw.secondary_error_summary || ''),
    topicCategory: normalizeTopicCategory(String(raw.topic_category || raw.topicCategory || analysis.topic_category || analysis.topicCategory || '')),
    recognitionStatus,
    recognitionStatusText: buildRecognitionStatusText(raw, recognitionStatus),
    isMastered: raw.is_mastered === true || raw.archive_status === 'archived',
    dateStr,
  };
}

function parseUploadTaskIds(value) {
  return decodeURIComponent(String(value || ''))
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeUploadTask(taskId, payloadTask) {
  const source = payloadTask && typeof payloadTask === 'object' ? payloadTask : {};
  const state = String(source.state || source.status || 'processing').trim();
  const status = state === 'ready' || state === 'failed' || state === 'pending' || state === 'processing'
    ? state
    : 'processing';
  return {
    ...source,
    id: taskId,
    status,
  };
}

function normalizeRecognitionStatus(raw) {
  const status = String((raw && (raw.recognition_status || raw.recognitionStatus)) || '').trim();
  if (status) {
    return status;
  }
  return String((raw && raw.question_text) || '').trim() ? 'recognized' : 'pending';
}

function buildRecognitionStatusText(raw, recognitionStatus) {
  const status = String(recognitionStatus || '').trim();
  const error = String((raw && (raw.recognition_error || raw.recognitionError)) || '').trim();
  if (status === 'failed') {
    return error ? `识别失败，原图已保留。原因：${error}` : '识别失败，原图已保留，老师会查看。';
  }
  if (status !== 'recognized') {
    return '服务器仍在识别，完成后会补上题目文本。';
  }
  return '';
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

function normalizeLibraryPdfState(serverUrl, payload, uploadTaskSummary, itemCount) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const totalItems = Number(source.total_items !== undefined ? source.total_items : itemCount) || 0;
  const pdfUrl = String(source.pdf_url || '').trim();
  const uploadState = String((uploadTaskSummary && uploadTaskSummary.state) || '').trim();
  if (pdfUrl && totalItems > 0) {
    return {
      url: /^https?:\/\//i.test(pdfUrl)
        ? pdfUrl
        : `${String(serverUrl || '').replace(/\/+$/, '')}${pdfUrl.startsWith('/') ? pdfUrl : `/${pdfUrl}`}`,
      ready: true,
      statusText: '',
    };
  }
  if (uploadState === 'background' || uploadState === 'pending') {
    return {
      url: '',
      ready: false,
      statusText: 'PDF 会在识别完成后生成，请稍后刷新错题本。',
    };
  }
  if (source.loadError) {
    return {
      url: '',
      ready: false,
      statusText: 'PDF 状态暂时无法刷新，请稍后重试。',
    };
  }
  if (totalItems > 0 && !pdfUrl) {
    return {
      url: '',
      ready: false,
      statusText: 'PDF 暂时不可用，请稍后刷新错题本。',
    };
  }
  return {
    url: '',
    ready: false,
    statusText: '',
  };
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
        reject(new Error('PDF 下载失败，请稍后刷新错题本再试'));
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
        reject(new Error('PDF 打开失败，请稍后重试或联系老师查看。'));
      },
    });
  });
}
