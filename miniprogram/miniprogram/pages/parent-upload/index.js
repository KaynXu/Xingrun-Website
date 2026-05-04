const app = getApp();
const {
  ensureParentSession,
  fetchParentBindings,
  fetchParentTopicCategorySuggestions,
  fetchWrongQuestionUploadTask,
  submitParentWrongQuestion,
  uploadParentReasonAudio,
} = require('../../utils/parentApi');
const { isPrimarySchoolBinding } = require('../../utils/classScope');
const {
  addManualBoxToImage,
  appendLocalImages,
  buildBoxTouchFrame,
  buildImageRotationPlan,
  buildUploadExportPlan,
  buildUploadJobs,
  buildUploadTaskSummary,
  getSubmitBlockers,
  normalizeDisplayBoxFrame,
  rotateImageBoxesClockwise,
} = require('./model');

const TASK_POLL_INTERVAL_MS = 2000;
const TASK_POLL_MAX_ATTEMPTS = 12;
const UPLOAD_TASK_RECOVERY_KEY_PREFIX = 'xr_parent_upload_tasks_v1';
const TOPIC_CATEGORY_OPTIONS = ['未分类', '计算', '经济', '浓度', '工程', '行程', '几何', '数论', '自定义'];
const CUSTOM_TOPIC_OPTION = '自定义';
const UNCLASSIFIED_TOPIC_CATEGORY = '未分类';
const UPLOAD_TASK_STATUS_MAP = {
  pending: true,
  processing: true,
  ready: true,
  failed: true,
};

function buildUploadTaskRecoveryStorageKey(openId, bindingId) {
  return `${UPLOAD_TASK_RECOVERY_KEY_PREFIX}:${String(openId || '').trim()}:${Number(bindingId) || 0}`;
}

function buildPendingUploadTask(taskId) {
  return {
    id: taskId,
    status: 'pending',
  };
}

function isTerminalUploadTask(task) {
  const status = String((task && task.status) || '').trim();
  return status === 'ready' || status === 'failed';
}

function normalizeRecoveryTaskEntry(task) {
  if (!task || typeof task !== 'object') {
    return null;
  }
  const id = task.id;
  if (id === undefined || id === null || !String(id).trim()) {
    return null;
  }
  const status = String(task.status || 'pending').trim();
  return {
    id,
    status: UPLOAD_TASK_STATUS_MAP[status] ? status : 'pending',
    imageId: String(task.imageId || ''),
    boxId: String(task.boxId || ''),
    topicCategory: String(task.topicCategory || '未分类').trim() || '未分类',
    acceptedAt: String(task.acceptedAt || ''),
  };
}

function parseRecoveryRecord(rawValue) {
  const record = typeof rawValue === 'string' ? JSON.parse(rawValue) : rawValue;
  if (!record || typeof record !== 'object' || !Array.isArray(record.tasks)) {
    throw new Error('invalid recovery record');
  }
  return record;
}

function normalizeFetchedUploadTask(taskId, payloadTask, previousTask) {
  const fallbackTask = previousTask || buildPendingUploadTask(taskId);
  if (!payloadTask || typeof payloadTask !== 'object') {
    return fallbackTask;
  }
  const payloadTaskId = payloadTask.id;
  if (payloadTaskId === undefined || payloadTaskId === null || String(payloadTaskId) !== String(taskId)) {
    return fallbackTask;
  }
  const status = String(payloadTask.status || '').trim();
  if (!UPLOAD_TASK_STATUS_MAP[status]) {
    return fallbackTask;
  }
  return {
    ...payloadTask,
    id: taskId,
    status,
  };
}

function buildTopicCategoryOptions(suggestions) {
  const seen = {};
  const options = [];
  TOPIC_CATEGORY_OPTIONS.forEach((item) => {
    if (item !== CUSTOM_TOPIC_OPTION && !seen[item]) {
      seen[item] = true;
      options.push(item);
    }
  });
  (Array.isArray(suggestions) ? suggestions : []).forEach((item) => {
    const topic = String(item || '').trim();
    if (topic && topic !== CUSTOM_TOPIC_OPTION && !seen[topic]) {
      seen[topic] = true;
      options.push(topic);
    }
  });
  options.push(CUSTOM_TOPIC_OPTION);
  return options;
}

Page({
  data: {
    binding: null,
    imageItems: [],
    selectedImageId: '',
    currentImage: null,
    activeBox: null,
    currentStatusText: '',
    displayBoxes: [],
    submitting: false,
    cropExporting: false,
    uploadStage: '',
    uploadStageTitle: '',
    uploadStageText: '',
    successTaskIds: [],
    uploadTaskSummary: null,
    errorMessage: '',
    stageWidth: 0,
    stageHeight: 0,
    imagePath: '',
    imageReady: false,
    loadError: false,
    imageLeft: 0,
    imageTop: 0,
    imageWidth: 0,
    imageHeight: 0,
    canvasWidth: 1,
    canvasHeight: 1,
    recordingBoxId: '',
    topicCategoryOptions: TOPIC_CATEGORY_OPTIONS,
    showPrimaryTopicCategory: false,
  },

  onLoad() {
    const systemInfo = wx.getSystemInfoSync();
    const stageWidth = Math.max(systemInfo.windowWidth - 56, 280);
    const stageHeight = Math.max(Math.floor(systemInfo.windowHeight * 0.48), 320);
    this.setData({
      stageWidth,
      stageHeight,
    });

    if (!wx.getRecorderManager) {
      return;
    }

    this.recorderManager = wx.getRecorderManager();
    this.recorderManager.onStop((response) => {
      const target = this.recordingTarget;
      this.recordingTarget = null;
      if (!target) {
        this.setData({ recordingBoxId: '' });
        return;
      }

      const voiceFilePath = response.tempFilePath || '';
      const imageItems = this.data.imageItems.map((item) => {
        if (item.id !== target.imageId) {
          return item;
        }
        return {
          ...item,
          boxes: (item.boxes || []).map((box) => {
            if (box.id !== target.boxId) {
              return box;
            }
            return {
              ...box,
              childReasonInputMode: 'voice',
              voiceFilePath,
              voiceFileName: voiceFilePath ? '已录制语音' : '',
              reasonStatusText: voiceFilePath ? '语音已保存，提交时会自动转成文字并归类。' : '录音没有成功保存，请重试。',
            };
          }),
        };
      });

      this.setData({ recordingBoxId: '' });
      void this.commitImageItems(imageItems, this.data.selectedImageId, false);
    });
    this.recorderManager.onError((error) => {
      this.recordingTarget = null;
      this.setData({
        recordingBoxId: '',
        errorMessage: (error && error.errMsg) || '录音失败，请重试。',
      });
    });
  },

  async onShow() {
    const bindingId = Number(this.options.bindingId || 0);

    try {
      const session = await ensureParentSession(wx, app.globalData.serverUrl);
      app.globalData.parentSession = session;
      const bindings = await fetchParentBindings(wx, app.globalData.serverUrl, {
        openId: session.openId,
      });
      const binding = bindings.find((item) => item.id === bindingId) || null;
      app.globalData.parentBindings = bindings;
      const showPrimaryTopicCategory = isPrimarySchoolBinding(binding);
      this.setData({
        binding,
        showPrimaryTopicCategory,
        topicCategoryOptions: TOPIC_CATEGORY_OPTIONS,
        errorMessage: binding ? '' : '没有找到这个孩子的最新绑定关系，请先重新绑定。',
      });
      if (binding) {
        if (showPrimaryTopicCategory) {
          await this.refreshTopicCategoryOptions(session.openId);
        }
        await this.restoreAcceptedUploadTasks(session.openId, binding);
      }
    } catch (error) {
      this.setData({
        binding: null,
        showPrimaryTopicCategory: false,
        topicCategoryOptions: TOPIC_CATEGORY_OPTIONS,
        errorMessage: error instanceof Error ? error.message : '绑定关系同步失败',
      });
    }
  },

  async refreshTopicCategoryOptions(openId) {
    try {
      const payload = await fetchParentTopicCategorySuggestions(wx, app.globalData.serverUrl, {
        openId,
        topicCategory: '',
      });
      this.setData({
        topicCategoryOptions: buildTopicCategoryOptions(payload && payload.items),
      });
    } catch (_error) {
      this.setData({
        topicCategoryOptions: TOPIC_CATEGORY_OPTIONS,
      });
    }
  },

  onUnload() {
    if (this.recorderManager && this.data.recordingBoxId) {
      this.recorderManager.stop();
    }
  },

  setDataAsync(data) {
    return new Promise((resolve) => {
      this.setData(data, resolve);
    });
  },

  wait(ms) {
    return new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  },

  setUploadStage(uploadStage, uploadStageText, uploadStageTitle) {
    this.setData({
      uploadStage,
      uploadStageText,
      uploadStageTitle: uploadStageTitle || '上传进度',
    });
  },

  isInteractionLocked() {
    return Boolean(this.data.submitting || this.data.cropExporting);
  },

  setUploadStageFromSummary(summary) {
    const currentSummary = summary || {};
    const state = String(currentSummary.state || 'pending');
    if (state === 'ready') {
      this.setUploadStage('ready', '识别完成，错题本已更新。', currentSummary.title || '识别完成');
      return;
    }
    if (state === 'background') {
      this.setUploadStage('background', currentSummary.description || '服务器会在云端继续识别，可以先离开本页，稍后可回错题本查看。', currentSummary.title || '已接收，云端识别中');
      return;
    }
    if (state === 'partial_failed') {
      this.setUploadStage('partial_failed', `${currentSummary.title || '部分识别失败'}：${currentSummary.description || '部分题目识别失败，其他题目仍保留。'}`, currentSummary.title || '部分识别失败');
      return;
    }
    if (state === 'failed') {
      this.setUploadStage('failed', `${currentSummary.title || '识别失败'}：${currentSummary.description || '请重新拍清楚一点。'}`, currentSummary.title || '识别失败');
      return;
    }
    this.setUploadStage('recognizing', `云端正在识别错题，${currentSummary.description || '完成后会进入错题本。'}`, currentSummary.title || '正在识别');
  },

  readAcceptedUploadTasks(openId, binding) {
    const bindingId = binding && binding.id;
    const key = buildUploadTaskRecoveryStorageKey(openId, bindingId);
    let record;
    let rawValue;
    if (typeof wx === 'undefined' || typeof wx.getStorageSync !== 'function') {
      return {
        key,
        tasks: [],
        errorMessage: '无法读取本机保存的上传进度，请稍后回错题本刷新。',
      };
    }

    try {
      rawValue = wx.getStorageSync(key);
    } catch (_error) {
      return {
        key,
        tasks: [],
        errorMessage: '无法读取本机保存的上传进度，请稍后回错题本刷新。',
      };
    }

    if (rawValue === '' || rawValue === undefined || rawValue === null) {
      return {
        key,
        tasks: [],
        errorMessage: '',
      };
    }

    try {
      record = parseRecoveryRecord(rawValue);
    } catch (_error) {
      return {
        key,
        tasks: [],
        errorMessage: '无法读取本机保存的上传进度，请稍后回错题本刷新。',
      };
    }

    if (String(record.openId || '') !== String(openId || '') || Number(record.bindingId || 0) !== Number(bindingId || 0)) {
      return {
        key,
        tasks: [],
        errorMessage: '',
      };
    }

    return {
      key,
      tasks: record.tasks.map(normalizeRecoveryTaskEntry).filter(Boolean),
      errorMessage: '',
    };
  },

  persistAcceptedUploadTasks(openId, binding, tasks) {
    const bindingId = binding && binding.id;
    const key = buildUploadTaskRecoveryStorageKey(openId, bindingId);
    const metadataById = this.uploadTaskRecoveryTasksById || {};
    const activeTasks = (Array.isArray(tasks) ? tasks : [])
      .map((task) => {
        const metadata = metadataById[String(task && task.id)] || {};
        return normalizeRecoveryTaskEntry({
          ...metadata,
          ...task,
        });
      })
      .filter((task) => task && !isTerminalUploadTask(task));

    if (!activeTasks.length) {
      if (typeof wx !== 'undefined' && typeof wx.removeStorageSync === 'function') {
        try {
          wx.removeStorageSync(key);
        } catch (_error) {
          return;
        }
      }
      return;
    }

    this.uploadTaskRecoveryTasksById = activeTasks.reduce((result, task) => {
      result[String(task.id)] = task;
      return result;
    }, {});

    if (typeof wx === 'undefined' || typeof wx.setStorageSync !== 'function') {
      return;
    }

    try {
      wx.setStorageSync(key, {
        version: 1,
        openId,
        bindingId: Number(bindingId) || 0,
        child: {
          studentName: String((binding && binding.studentName) || ''),
          className: String((binding && binding.className) || ''),
        },
        tasks: activeTasks,
        updatedAt: new Date().toISOString(),
      });
    } catch (_error) {
      this.setUploadStage('background', '本机暂时不能保存上传进度，请稍后回错题本刷新。', '上传进度待刷新');
    }
  },

  async restoreAcceptedUploadTasks(openId, binding) {
    const recovered = this.readAcceptedUploadTasks(openId, binding);
    const tasks = recovered.tasks || [];
    if (recovered.errorMessage) {
      this.setUploadStage('background', recovered.errorMessage, '上传进度待刷新');
      return null;
    }
    if (!tasks.length) {
      return null;
    }

    this.uploadTaskRecoveryTasksById = tasks.reduce((result, task) => {
      result[String(task.id)] = task;
      return result;
    }, {});

    const taskIds = tasks.map((task) => task.id);
    this.setData({
      successTaskIds: taskIds,
      uploadTaskSummary: buildUploadTaskSummary(tasks),
      errorMessage: '',
    });
    this.setUploadStage('background', `找到 ${taskIds.length} 条此前已接收的上传任务，正在刷新状态。`, '正在恢复上传进度');
    const summary = await this.pollUploadTasks(openId, taskIds);
    this.setData({
      successTaskIds: taskIds,
      uploadTaskSummary: summary,
    });
    return summary;
  },

  getCurrentImageFrom(imageItems, selectedImageId) {
    return (imageItems || []).find((item) => item.id === selectedImageId) || null;
  },

  buildStatusText(currentImage) {
    const image = currentImage || null;
    if (!image) {
      return '';
    }
    if ((image.boxes || []).length) {
      return `当前已框 ${(image.boxes || []).length} 题，可直接拖动框和四角调整。`;
    }
    return '先补加题框后再提交。';
  },

  buildLayout(sourceWidth, sourceHeight) {
    const stageWidth = this.data.stageWidth;
    const stageHeight = this.data.stageHeight;
    const scale = Math.min(stageWidth / sourceWidth, stageHeight / sourceHeight);
    const imageWidth = Math.floor(sourceWidth * scale);
    const imageHeight = Math.floor(sourceHeight * scale);
    const imageLeft = Math.floor((stageWidth - imageWidth) / 2);
    const imageTop = Math.floor((stageHeight - imageHeight) / 2);

    return {
      imageLeft,
      imageTop,
      imageWidth,
      imageHeight,
    };
  },

  buildDisplayBoxes(currentImage) {
    const image = currentImage || null;
    if (!image || !this.data.imageWidth || !this.data.imageHeight) {
      return [];
    }

    return (image.boxes || []).map((box, index) => {
      return {
        id: box.id,
        label: `题 ${index + 1}`,
        left: Math.round(this.data.imageLeft + box.x * this.data.imageWidth),
        top: Math.round(this.data.imageTop + box.y * this.data.imageHeight),
        width: Math.round(box.width * this.data.imageWidth),
        height: Math.round(box.height * this.data.imageHeight),
        active: box.id === image.activeBoxId,
      };
    });
  },

  async commitImageItems(imageItems, selectedImageId, shouldReloadStage) {
    const currentImage = this.getCurrentImageFrom(imageItems, selectedImageId);
    const activeBox = currentImage && currentImage.activeBoxId
      ? (currentImage.boxes || []).find((box) => box.id === currentImage.activeBoxId) || null
      : null;
    await this.setDataAsync({
      imageItems,
      selectedImageId,
      currentImage,
      activeBox,
      currentStatusText: this.buildStatusText(currentImage),
      successTaskIds: [],
      uploadTaskSummary: null,
      uploadStage: '',
      uploadStageTitle: '',
      uploadStageText: '',
    });

    if (shouldReloadStage) {
      await this.loadCurrentImage();
      return;
    }

    await this.setDataAsync({
      displayBoxes: this.buildDisplayBoxes(currentImage),
      currentStatusText: this.buildStatusText(currentImage),
    });
  },

  async loadCurrentImage() {
    const currentImage = this.getCurrentImageFrom(this.data.imageItems, this.data.selectedImageId);
    if (!currentImage || !currentImage.localPath) {
      this.currentImageInfo = null;
      await this.setDataAsync({
        currentImage: null,
        activeBox: null,
        imagePath: '',
        imageReady: false,
        loadError: false,
        displayBoxes: [],
        currentStatusText: '',
      });
      return;
    }

    try {
      const imageInfo = await this.getImageInfo(currentImage.localPath);
      const layout = this.buildLayout(imageInfo.width, imageInfo.height);
      this.currentImageInfo = {
        filePath: currentImage.localPath,
        width: imageInfo.width,
        height: imageInfo.height,
      };
      await this.setDataAsync({
        currentImage,
        activeBox: currentImage.activeBoxId ? (currentImage.boxes || []).find((box) => box.id === currentImage.activeBoxId) || null : null,
        imagePath: currentImage.localPath,
        imageReady: true,
        loadError: false,
        imageLeft: layout.imageLeft,
        imageTop: layout.imageTop,
        imageWidth: layout.imageWidth,
        imageHeight: layout.imageHeight,
        displayBoxes: this.buildDisplayBoxes(currentImage),
        currentStatusText: this.buildStatusText(currentImage),
      });
    } catch (_error) {
      this.currentImageInfo = null;
      await this.setDataAsync({
        currentImage,
        activeBox: currentImage.activeBoxId ? (currentImage.boxes || []).find((box) => box.id === currentImage.activeBoxId) || null : null,
        imagePath: currentImage.localPath,
        imageReady: false,
        loadError: true,
        displayBoxes: [],
        currentStatusText: '图片没有正确加载出来，可以重新选择或稍后再试。',
      });
    }
  },

  getImageInfo(src) {
    return new Promise((resolve, reject) => {
      wx.getImageInfo({
        src,
        success: resolve,
        fail: reject,
      });
    });
  },

  async exportCanvasImage(filePath, options) {
    const runExport = async () => {
      const canvasWidth = Math.max(1, Math.round(Number(options && options.canvasWidth) || 0));
      const canvasHeight = Math.max(1, Math.round(Number(options && options.canvasHeight) || 0));
      const drawWidth = Math.max(1, Math.round(Number(options && options.drawWidth) || canvasWidth));
      const drawHeight = Math.max(1, Math.round(Number(options && options.drawHeight) || canvasHeight));
      const translateX = Math.round(Number(options && options.translateX) || 0);
      const translateY = Math.round(Number(options && options.translateY) || 0);
      const rotationRadians = Number(options && options.rotationRadians) || 0;
      const backgroundColor = String((options && options.backgroundColor) || '#ffffff');
      const fileType = String((options && options.fileType) || 'jpg');
      const quality = Math.max(0.1, Math.min(1, Number(options && options.quality) || 1));
      const sourceRect = options && options.sourceRect ? options.sourceRect : null;

      await this.setDataAsync({
        canvasWidth,
        canvasHeight,
      });
      await this.wait(60);

      return new Promise((resolve, reject) => {
        const ctx = wx.createCanvasContext('cropCanvas', this);
        ctx.clearRect(0, 0, canvasWidth, canvasHeight);
        ctx.setFillStyle(backgroundColor);
        ctx.fillRect(0, 0, canvasWidth, canvasHeight);
        ctx.save();

        if (translateX || translateY) {
          ctx.translate(translateX, translateY);
        }
        if (rotationRadians) {
          ctx.rotate(rotationRadians);
        }

        if (sourceRect) {
          ctx.drawImage(
            filePath,
            sourceRect.x,
            sourceRect.y,
            sourceRect.width,
            sourceRect.height,
            0,
            0,
            drawWidth,
            drawHeight
          );
        } else {
          ctx.drawImage(filePath, 0, 0, drawWidth, drawHeight);
        }

        ctx.restore();
        ctx.draw(false, () => {
          setTimeout(() => {
            wx.canvasToTempFilePath({
              canvasId: 'cropCanvas',
              x: 0,
              y: 0,
              width: canvasWidth,
              height: canvasHeight,
              destWidth: canvasWidth,
              destHeight: canvasHeight,
              fileType,
              quality,
              success: (response) => resolve(response.tempFilePath),
              fail: reject,
            }, this);
          }, 60);
        });
      });
    };

    const previousExport = this.canvasExportChain || Promise.resolve();
    const nextExport = previousExport.catch(() => null).then(runExport);
    this.canvasExportChain = nextExport;
    return nextExport;
  },

  chooseImages() {
    if (this.isInteractionLocked()) {
      return;
    }
    wx.chooseImage({
      count: 9,
      sizeType: ['original'],
      sourceType: ['camera', 'album'],
      success: async (response) => {
        const nextPaths = response.tempFilePaths || [];
        const imageItems = appendLocalImages(this.data.imageItems, nextPaths);
        const selectedImageId = nextPaths.length
          ? ((imageItems[imageItems.length - 1] && imageItems[imageItems.length - 1].id) || '')
          : (this.data.selectedImageId || (imageItems[0] && imageItems[0].id) || '');
        await this.commitImageItems(imageItems, selectedImageId, true);
        this.setData({
          errorMessage: '',
        });
      },
      fail: (error) => {
        this.setData({
          errorMessage: (error && error.errMsg) || '选择图片失败',
        });
      },
    });
  },

  async selectImage(event) {
    if (this.isInteractionLocked()) {
      return;
    }
    const selectedImageId = String(event.currentTarget.dataset.imageId || '');
    if (!selectedImageId || selectedImageId === this.data.selectedImageId) {
      return;
    }
    await this.commitImageItems(this.data.imageItems, selectedImageId, true);
  },

  async addManualBox() {
    if (this.isInteractionLocked()) {
      return;
    }
    if (!this.data.selectedImageId) {
      return;
    }

    const imageItems = this.data.imageItems.map((item) => {
      if (item.id !== this.data.selectedImageId) {
        return item;
      }
      return addManualBoxToImage(item);
    });
    await this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  async selectBox(event) {
    if (this.isInteractionLocked()) {
      return;
    }
    const boxId = String(event.currentTarget.dataset.boxId || '');
    if (!boxId || !this.data.currentImage) {
      return;
    }

    const currentImageId = this.data.currentImage.id;
    const imageItems = this.data.imageItems.map((item) => {
      if (item.id !== currentImageId) {
        return item;
      }
      return {
        ...item,
        boxes: item.boxes || [],
        activeBoxId: boxId,
      };
    });
    await this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  handleActiveBoxReasonInput(event) {
    const nextReasonText = String(event.detail.value || '');
    const currentImage = this.data.currentImage;
    if (!currentImage || !currentImage.activeBoxId) {
      return;
    }

    const imageItems = this.data.imageItems.map((item) => {
      if (item.id !== currentImage.id) {
        return item;
      }

      return {
        ...item,
        boxes: (item.boxes || []).map((box) => {
          if (box.id !== currentImage.activeBoxId) {
            return box;
          }
          return {
            ...box,
            childReasonText: nextReasonText,
            reasonStatusText: '',
          };
        }),
      };
    });

    void this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  handleActiveBoxTopicChange(event) {
    if (!this.data.showPrimaryTopicCategory) {
      return;
    }
    const index = Number(event && event.detail ? event.detail.value : 0);
    const options = this.data.topicCategoryOptions || TOPIC_CATEGORY_OPTIONS;
    const nextTopic = options[index] || UNCLASSIFIED_TOPIC_CATEGORY;
    const currentImage = this.data.currentImage;
    if (!currentImage || !currentImage.activeBoxId) {
      return;
    }

    const imageItems = this.data.imageItems.map((item) => {
      if (item.id !== currentImage.id) {
        return item;
      }

      return {
        ...item,
        boxes: (item.boxes || []).map((box) => {
          if (box.id !== currentImage.activeBoxId) {
            return box;
          }
          return {
            ...box,
            topicCategory: nextTopic === CUSTOM_TOPIC_OPTION ? '' : nextTopic,
          };
        }),
      };
    });

    void this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  handleActiveBoxCustomTopicInput(event) {
    if (!this.data.showPrimaryTopicCategory) {
      return;
    }
    const nextTopic = String(event && event.detail ? event.detail.value : '').trim();
    const currentImage = this.data.currentImage;
    if (!currentImage || !currentImage.activeBoxId) {
      return;
    }

    const imageItems = this.data.imageItems.map((item) => {
      if (item.id !== currentImage.id) {
        return item;
      }

      return {
        ...item,
        boxes: (item.boxes || []).map((box) => {
          if (box.id !== currentImage.activeBoxId) {
            return box;
          }
          return {
            ...box,
            topicCategory: nextTopic,
          };
        }),
      };
    });

    void this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  switchActiveBoxReasonMode(event) {
    const dataset = event && event.currentTarget ? event.currentTarget.dataset : null;
    const nextMode = dataset && dataset.mode === 'voice' ? 'voice' : 'text';
    const currentImage = this.data.currentImage;
    if (!currentImage || !currentImage.activeBoxId) {
      return;
    }

    const imageItems = this.data.imageItems.map((item) => {
      if (item.id !== currentImage.id) {
        return item;
      }

      return {
        ...item,
        boxes: (item.boxes || []).map((box) => {
          if (box.id !== currentImage.activeBoxId) {
            return box;
          }
          return {
            ...box,
            childReasonInputMode: nextMode,
            reasonStatusText: nextMode === 'voice'
              ? (box.reasonStatusText || '录一段孩子自己的说明，提交时会自动转成老师可读的文字。')
              : '',
          };
        }),
      };
    });

    void this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  toggleActiveBoxVoiceRecording() {
    const currentImage = this.data.currentImage;
    const activeBox = this.data.activeBox;
    if (!currentImage || !activeBox) {
      wx.showToast({ title: '请先选中一道题', icon: 'none' });
      return;
    }
    if (!this.recorderManager) {
      wx.showToast({ title: '当前微信版本不支持录音', icon: 'none' });
      return;
    }

    if (this.data.recordingBoxId === activeBox.id) {
      this.recorderManager.stop();
      this.setData({ recordingBoxId: '' });
      return;
    }

    this.recordingTarget = {
      imageId: currentImage.id,
      boxId: activeBox.id,
    };
    this.setData({
      recordingBoxId: activeBox.id,
      errorMessage: '',
    });

    const imageItems = this.data.imageItems.map((item) => {
      if (item.id !== currentImage.id) {
        return item;
      }
      return {
        ...item,
        boxes: (item.boxes || []).map((box) => {
          if (box.id !== activeBox.id) {
            return box;
          }
          return {
            ...box,
            childReasonInputMode: 'voice',
            reasonStatusText: '录音中，再点一次结束。',
          };
        }),
      };
    });

    void this.commitImageItems(imageItems, this.data.selectedImageId, false);
    this.recorderManager.start({
      duration: 60000,
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 96000,
      format: 'mp3',
    });
  },

  async removeActiveBox() {
    if (this.isInteractionLocked()) {
      return;
    }
    if (!this.data.selectedImageId || !this.data.currentImage) {
      return;
    }

    const currentImageId = this.data.currentImage.id;
    const imageItems = this.data.imageItems.map((item) => {
      let boxes;
      let activeBoxIndex;
      let nextActiveBoxIndex;
      if (item.id !== currentImageId) {
        return item;
      }
      activeBoxIndex = (item.boxes || []).findIndex((box) => box.id === item.activeBoxId);
      boxes = (item.boxes || []).filter((box) => box.id !== item.activeBoxId);
      nextActiveBoxIndex = activeBoxIndex >= 0 ? Math.min(activeBoxIndex, boxes.length - 1) : 0;
      return {
        ...item,
        boxes,
        activeBoxId: boxes[nextActiveBoxIndex] ? boxes[nextActiveBoxIndex].id : '',
      };
    });
    await this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  getDisplayBox(boxId) {
    return (this.data.displayBoxes || []).find((item) => item.id === boxId) || null;
  },

  async updateBoxDisplay(boxId, nextLeft, nextTop, nextWidth, nextHeight) {
    const currentImage = this.data.currentImage;
    if (!currentImage || !boxId || !this.data.imageWidth || !this.data.imageHeight) {
      return;
    }

    const normalizedBox = normalizeDisplayBoxFrame({
      left: nextLeft,
      top: nextTop,
      width: nextWidth,
      height: nextHeight,
      imageLeft: this.data.imageLeft,
      imageTop: this.data.imageTop,
      imageWidth: this.data.imageWidth,
      imageHeight: this.data.imageHeight,
    });

    const imageItems = this.data.imageItems.map((item) => {
      if (item.id !== currentImage.id) {
        return item;
      }
      return {
        ...item,
        boxes: (item.boxes || []).map((box) => {
          if (box.id !== boxId) {
            return box;
          }
          return {
            ...box,
            x: normalizedBox.x,
            y: normalizedBox.y,
            width: normalizedBox.width,
            height: normalizedBox.height,
          };
        }),
        activeBoxId: boxId,
      };
    });

    await this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  onBoxTouchStart(event) {
    if (this.isInteractionLocked()) {
      this.touchState = null;
      return;
    }
    const touch = event.touches[0];
    const boxId = String(event.currentTarget.dataset.boxId || '');
    const mode = String(event.currentTarget.dataset.mode || 'move');
    const displayBox = this.getDisplayBox(boxId);
    if (!touch || !boxId || !displayBox) {
      return;
    }

    this.touchState = {
      boxId,
      mode,
      startX: touch.clientX,
      startY: touch.clientY,
      left: displayBox.left,
      top: displayBox.top,
      width: displayBox.width,
      height: displayBox.height,
    };
  },

  onBoxTouchMove(event) {
    if (this.isInteractionLocked()) {
      this.touchState = null;
      return;
    }
    if (!this.touchState) {
      return;
    }

    const touch = event.touches[0];
    if (!touch) {
      return;
    }
    const deltaX = touch.clientX - this.touchState.startX;
    const deltaY = touch.clientY - this.touchState.startY;
    const nextFrame = buildBoxTouchFrame({
      mode: this.touchState.mode,
      startLeft: this.touchState.left,
      startTop: this.touchState.top,
      startWidth: this.touchState.width,
      startHeight: this.touchState.height,
      deltaX,
      deltaY,
      imageLeft: this.data.imageLeft,
      imageTop: this.data.imageTop,
      imageWidth: this.data.imageWidth,
      imageHeight: this.data.imageHeight,
    });

    this.updateBoxDisplay(this.touchState.boxId, nextFrame.left, nextFrame.top, nextFrame.width, nextFrame.height);
  },

  onBoxTouchEnd() {
    this.touchState = null;
  },

  async updateImageItem(imageId, updater) {
    const imageItems = this.data.imageItems.map((item) => {
      if (item.id !== imageId) {
        return item;
      }
      return updater(item);
    });
    await this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  async rotateCurrentImageClockwise() {
    const currentImage = this.data.currentImage;
    let imageInfo;
    let rotationPlan;
    let rotatedPath;
    let imageItems;
    if (!currentImage || !currentImage.localPath) {
      return;
    }
    if (this.isInteractionLocked()) {
      return;
    }

    this.setData({
      errorMessage: '',
      cropExporting: true,
    });

    try {
      imageInfo = await this.getImageInfo(currentImage.localPath);
      rotationPlan = buildImageRotationPlan({
        width: imageInfo.width,
        height: imageInfo.height,
        quarterTurns: 1,
      });
      rotatedPath = await this.exportCanvasImage(currentImage.localPath, {
        canvasWidth: rotationPlan.canvasWidth,
        canvasHeight: rotationPlan.canvasHeight,
        drawWidth: imageInfo.width,
        drawHeight: imageInfo.height,
        translateX: rotationPlan.translateX,
        translateY: rotationPlan.translateY,
        rotationRadians: rotationPlan.rotationRadians,
        backgroundColor: rotationPlan.backgroundColor,
      });
      imageItems = this.data.imageItems.map((item) => {
        if (item.id !== currentImage.id) {
          return item;
        }
        return rotateImageBoxesClockwise({
          ...item,
          localPath: rotatedPath,
        });
      });
      await this.commitImageItems(imageItems, currentImage.id, true);
    } catch (error) {
      this.setData({
        errorMessage: error instanceof Error ? error.message : '旋转图片失败，请稍后重试。',
      });
    } finally {
      this.setData({
        cropExporting: false,
      });
    }
  },

  async exportBoxCrop(imageItem, box) {
    const imageInfo = await this.getImageInfo(imageItem.localPath);
    const cropX = Math.max(0, Math.round(box.x * imageInfo.width));
    const cropY = Math.max(0, Math.round(box.y * imageInfo.height));
    const cropWidth = Math.max(1, Math.round(box.width * imageInfo.width));
    const cropHeight = Math.max(1, Math.round(box.height * imageInfo.height));
    const exportPlan = buildUploadExportPlan({ cropWidth, cropHeight });

    return this.exportCanvasImage(imageItem.localPath, {
      canvasWidth: exportPlan.outputWidth,
      canvasHeight: exportPlan.outputHeight,
      drawWidth: exportPlan.outputWidth,
      drawHeight: exportPlan.outputHeight,
      backgroundColor: '#ffffff',
      quality: exportPlan.quality,
      sourceRect: {
        x: cropX,
        y: cropY,
        width: cropWidth,
        height: cropHeight,
      },
    });
  },

  async submitUpload() {
    let jobs;
    const successTaskIds = [];
    const acceptedUploadTasks = [];
    if (this.isInteractionLocked()) {
      return;
    }
    if (!this.data.binding || !this.data.binding.id) {
      wx.showToast({ title: '请先绑定孩子', icon: 'none' });
      return;
    }
    if (!(this.data.imageItems || []).length) {
      wx.showToast({ title: '请先选择错题图片', icon: 'none' });
      return;
    }

    const blockers = getSubmitBlockers(this.data.imageItems);
    if (blockers.emptyImageIds.length) {
      wx.showToast({ title: '还有图片未补框', icon: 'none' });
      return;
    }
    if (blockers.missingReasonBoxIds.length) {
      wx.showToast({ title: '每题都要填写为什么错', icon: 'none' });
      return;
    }

    jobs = buildUploadJobs(this.data.imageItems);
    if (!jobs.length) {
      wx.showToast({ title: '请先框出错题范围', icon: 'none' });
      return;
    }

    this.setData({
      submitting: true,
      errorMessage: '',
    });

    try {
      const session = await ensureParentSession(wx, app.globalData.serverUrl);
      let currentJob;
      let imageItem;
      let croppedPath;
      let payload;
      let audioPayload;
      let childReasonAudioUrl;

      app.globalData.parentSession = session;

      for (currentJob of jobs) {
        const jobIndex = successTaskIds.length + 1;
        const jobLabel = `第 ${jobIndex}/${jobs.length} 题`;
        imageItem = this.data.imageItems.find((item) => item.id === currentJob.imageId);
        if (!imageItem) {
          continue;
        }
        this.setUploadStage('preparing_crop', `正在裁切${jobLabel}，请勿退出页面。`, '正在准备题图');
        this.setData({ cropExporting: true });
        try {
          croppedPath = await this.exportBoxCrop(imageItem, currentJob.box);
        } catch (error) {
          const message = error instanceof Error ? error.message : '裁切图片失败，请重试。';
          throw new Error(`${jobLabel}裁切失败：${message}`);
        } finally {
          this.setData({ cropExporting: false });
        }
        childReasonAudioUrl = '';

        if (currentJob.childReasonInputMode === 'voice') {
          this.setUploadStage('uploading_audio', `正在上传${jobLabel}的语音说明。`, '正在上传语音');
          audioPayload = await uploadParentReasonAudio(wx, app.globalData.serverUrl, {
            filePath: currentJob.voiceFilePath,
          });
          childReasonAudioUrl = String(audioPayload.audioUrl || '').trim();
        }

        this.setUploadStage('uploading_image', `正在上传${jobLabel}题图并提交识别任务。`, '正在上传题图');
        payload = await submitParentWrongQuestion(wx, app.globalData.serverUrl, {
          openId: session.openId,
          bindingId: this.data.binding.id,
          filePath: croppedPath,
          childReasonText: String(currentJob.childRawReasonText || '').trim(),
          childReasonInputMode: currentJob.childReasonInputMode,
          childReasonAudioUrl,
          topicCategory: this.data.showPrimaryTopicCategory ? currentJob.topicCategory : UNCLASSIFIED_TOPIC_CATEGORY,
        });
        const taskId = (payload.task && payload.task.id) || '';
        if (!String(taskId).trim()) {
          throw new Error('服务器没有返回上传任务编号，请稍后重试。');
        }
        successTaskIds.push(taskId);
        acceptedUploadTasks.push({
          id: taskId,
          status: 'pending',
          imageId: currentJob.imageId,
          boxId: currentJob.boxId,
          topicCategory: this.data.showPrimaryTopicCategory ? currentJob.topicCategory : UNCLASSIFIED_TOPIC_CATEGORY,
          acceptedAt: new Date().toISOString(),
        });
        this.uploadTaskRecoveryTasksById = acceptedUploadTasks.reduce((result, task) => {
          result[String(task.id)] = task;
          return result;
        }, {});
        this.persistAcceptedUploadTasks(session.openId, this.data.binding, acceptedUploadTasks);
        this.setUploadStage('task_accepted', `${jobLabel}已接收${taskId ? `，任务 ${taskId}` : ''}。`, '任务已接收');
      }

      this.setData({
        successTaskIds,
        uploadTaskSummary: buildUploadTaskSummary(successTaskIds.map((id) => ({ id, status: 'pending' })), { background: true }),
        imageItems: [],
        selectedImageId: '',
        currentImage: null,
        currentStatusText: '',
        displayBoxes: [],
        imagePath: '',
        imageReady: false,
        loadError: false,
        activeBox: null,
      });
      wx.showToast({
        title: '已接收',
        icon: 'none',
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '上传失败';
      if (successTaskIds.length) {
        const uploadTaskSummary = buildUploadTaskSummary(acceptedUploadTasks, { background: true });
        this.setData({
          errorMessage,
          successTaskIds,
          uploadTaskSummary,
        });
        this.setUploadStage('background', `已接收 ${successTaskIds.length} 条上传任务，后续提交中断：${errorMessage}。已接收的任务会继续保留，可稍后回错题本查看。`, '部分任务已接收');
      } else {
        this.setData({
          errorMessage,
        });
        this.setUploadStage('failed', `上传中断：${errorMessage}`, '上传失败');
      }
    } finally {
      this.setData({ submitting: false });
    }
  },

  waitForUploadTaskPoll() {
    return new Promise((resolve) => {
      setTimeout(resolve, TASK_POLL_INTERVAL_MS);
    });
  },

  async pollUploadTasks(openId, taskIds) {
    const ids = (Array.isArray(taskIds) ? taskIds : []).filter((id) => id !== undefined && id !== null && String(id).trim());
    let tasks = ids.map((id) => buildPendingUploadTask(id));
    let summary = buildUploadTaskSummary(tasks);
    this.setData({ uploadTaskSummary: summary });
    this.setUploadStageFromSummary(summary);

    for (let attempt = 0; attempt < TASK_POLL_MAX_ATTEMPTS; attempt += 1) {
      const previousTasksById = tasks.reduce((result, task) => {
        result[String(task.id)] = task;
        return result;
      }, {});
      tasks = await Promise.all(ids.map(async (taskId) => {
        const previousTask = previousTasksById[String(taskId)] || buildPendingUploadTask(taskId);
        try {
          const payload = await fetchWrongQuestionUploadTask(wx, app.globalData.serverUrl, {
            openId,
            taskId,
          });
          return normalizeFetchedUploadTask(taskId, payload && payload.task, previousTask);
        } catch (_error) {
          return previousTask;
        }
      }));
      summary = buildUploadTaskSummary(tasks);
      this.setData({ uploadTaskSummary: summary });
      this.persistAcceptedUploadTasks(openId, this.data.binding, tasks);
      this.setUploadStageFromSummary(summary);

      if ((summary.state === 'ready' || summary.state === 'failed' || summary.state === 'partial_failed') && summary.pendingCount === 0) {
        return summary;
      }
      await this.waitForUploadTaskPoll();
    }

    summary = buildUploadTaskSummary(tasks, { background: true });
    this.setData({ uploadTaskSummary: summary });
    this.persistAcceptedUploadTasks(openId, this.data.binding, tasks);
    this.setUploadStageFromSummary(summary);
    return summary;
  },

  openChildWrongbook() {
    const binding = this.data.binding || {};
    const studentId = Number(binding.studentId || binding.student_id || 0) || 0;
    const studentName = String(binding.studentName || binding.student_name || '').trim();
    const taskIds = (this.data.successTaskIds || [])
      .filter((id) => id !== undefined && id !== null && String(id).trim())
      .map((id) => String(id).trim())
      .join(',');
    const query = [`studentId=${studentId}`];
    if (!studentId) {
      wx.showToast({ title: '没有找到孩子信息', icon: 'none' });
      return;
    }
    if (studentName) {
      query.push(`studentName=${encodeURIComponent(studentName)}`);
    }
    if (binding.className || binding.class_name) {
      query.push(`className=${encodeURIComponent(String(binding.className || binding.class_name || '').trim())}`);
    }
    if (binding.classGrade || binding.class_grade || binding.grade) {
      query.push(`classGrade=${encodeURIComponent(String(binding.classGrade || binding.class_grade || binding.grade || '').trim())}`);
    }
    if (taskIds) {
      query.push(`uploadTaskIds=${encodeURIComponent(taskIds)}`);
    }
    wx.navigateTo({ url: `/pages/parent-wrongbook/index?${query.join('&')}` });
  },

  backHome() {
    wx.reLaunch({ url: '/pages/parent-home/index' });
  },
});
