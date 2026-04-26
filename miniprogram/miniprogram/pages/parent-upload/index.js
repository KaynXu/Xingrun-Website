const app = getApp();
const {
  ensureParentSession,
  fetchParentBindings,
  submitParentWrongQuestion,
  uploadParentReasonAudio,
} = require('../../utils/parentApi');
const {
  addManualBoxToImage,
  appendLocalImages,
  buildImageRotationPlan,
  buildUploadJobs,
  getSubmitBlockers,
  rotateImageBoxesClockwise,
} = require('./model');

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
    successTaskIds: [],
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
      this.setData({
        binding,
        errorMessage: binding ? '' : '没有找到这个孩子的最新绑定关系，请先重新绑定。',
      });
    } catch (error) {
      this.setData({
        binding: null,
        errorMessage: error instanceof Error ? error.message : '绑定关系同步失败',
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
    const selectedImageId = String(event.currentTarget.dataset.imageId || '');
    if (!selectedImageId || selectedImageId === this.data.selectedImageId) {
      return;
    }
    await this.commitImageItems(this.data.imageItems, selectedImageId, true);
  },

  async addManualBox() {
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
    if (!this.data.selectedImageId || !this.data.currentImage) {
      return;
    }

    const currentImageId = this.data.currentImage.id;
    const imageItems = this.data.imageItems.map((item) => {
      let boxes;
      if (item.id !== currentImageId) {
        return item;
      }
      boxes = (item.boxes || []).filter((box) => box.id !== item.activeBoxId);
      return {
        ...item,
        boxes,
        activeBoxId: boxes[0] ? boxes[0].id : '',
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

    const normalizedBox = {
      x: (nextLeft - this.data.imageLeft) / this.data.imageWidth,
      y: (nextTop - this.data.imageTop) / this.data.imageHeight,
      width: nextWidth / this.data.imageWidth,
      height: nextHeight / this.data.imageHeight,
    };

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
            x: Math.max(0, Math.min(normalizedBox.x, 1)),
            y: Math.max(0, Math.min(normalizedBox.y, 1)),
            width: Math.max(0.08, Math.min(normalizedBox.width, 1)),
            height: Math.max(0.08, Math.min(normalizedBox.height, 1)),
          };
        }),
        activeBoxId: boxId,
      };
    });

    await this.commitImageItems(imageItems, this.data.selectedImageId, false);
  },

  onBoxTouchStart(event) {
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
    if (!this.touchState) {
      return;
    }

    const touch = event.touches[0];
    const deltaX = touch.clientX - this.touchState.startX;
    const deltaY = touch.clientY - this.touchState.startY;
    const minSize = 72;
    const imageRight = this.data.imageLeft + this.data.imageWidth;
    const imageBottom = this.data.imageTop + this.data.imageHeight;

    let nextLeft = this.touchState.left;
    let nextTop = this.touchState.top;
    let nextWidth = this.touchState.width;
    let nextHeight = this.touchState.height;

    if (this.touchState.mode === 'move') {
      nextLeft = this.touchState.left + deltaX;
      nextTop = this.touchState.top + deltaY;
      nextLeft = Math.max(this.data.imageLeft, Math.min(nextLeft, imageRight - nextWidth));
      nextTop = Math.max(this.data.imageTop, Math.min(nextTop, imageBottom - nextHeight));
    } else if (this.touchState.mode === 'resize-se') {
      nextWidth = Math.max(minSize, Math.min(this.touchState.width + deltaX, imageRight - this.touchState.left));
      nextHeight = Math.max(minSize, Math.min(this.touchState.height + deltaY, imageBottom - this.touchState.top));
    } else if (this.touchState.mode === 'resize-sw') {
      nextLeft = Math.max(this.data.imageLeft, Math.min(this.touchState.left + deltaX, this.touchState.left + this.touchState.width - minSize));
      nextWidth = this.touchState.width + (this.touchState.left - nextLeft);
      nextHeight = Math.max(minSize, Math.min(this.touchState.height + deltaY, imageBottom - this.touchState.top));
    } else if (this.touchState.mode === 'resize-ne') {
      nextTop = Math.max(this.data.imageTop, Math.min(this.touchState.top + deltaY, this.touchState.top + this.touchState.height - minSize));
      nextWidth = Math.max(minSize, Math.min(this.touchState.width + deltaX, imageRight - this.touchState.left));
      nextHeight = this.touchState.height + (this.touchState.top - nextTop);
    } else if (this.touchState.mode === 'resize-nw') {
      nextLeft = Math.max(this.data.imageLeft, Math.min(this.touchState.left + deltaX, this.touchState.left + this.touchState.width - minSize));
      nextTop = Math.max(this.data.imageTop, Math.min(this.touchState.top + deltaY, this.touchState.top + this.touchState.height - minSize));
      nextWidth = this.touchState.width + (this.touchState.left - nextLeft);
      nextHeight = this.touchState.height + (this.touchState.top - nextTop);
    }

    this.updateBoxDisplay(this.touchState.boxId, nextLeft, nextTop, nextWidth, nextHeight);
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

    this.setData({
      errorMessage: '',
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
    }
  },

  async exportBoxCrop(imageItem, box) {
    const imageInfo = await this.getImageInfo(imageItem.localPath);
    const cropX = Math.max(0, Math.round(box.x * imageInfo.width));
    const cropY = Math.max(0, Math.round(box.y * imageInfo.height));
    const cropWidth = Math.max(1, Math.round(box.width * imageInfo.width));
    const cropHeight = Math.max(1, Math.round(box.height * imageInfo.height));
    const outputWidth = Math.min(cropWidth, 1800);
    const outputHeight = Math.max(1, Math.round((cropHeight / cropWidth) * outputWidth));

    return this.exportCanvasImage(imageItem.localPath, {
      canvasWidth: outputWidth,
      canvasHeight: outputHeight,
      drawWidth: outputWidth,
      drawHeight: outputHeight,
      backgroundColor: '#ffffff',
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
    if (this.data.submitting) {
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
      const successTaskIds = [];
      let currentJob;
      let imageItem;
      let croppedPath;
      let payload;
      let audioPayload;
      let childReasonAudioUrl;

      app.globalData.parentSession = session;

      for (currentJob of jobs) {
        imageItem = this.data.imageItems.find((item) => item.id === currentJob.imageId);
        if (!imageItem) {
          continue;
        }
        croppedPath = await this.exportBoxCrop(imageItem, currentJob.box);
        childReasonAudioUrl = '';

        if (currentJob.childReasonInputMode === 'voice') {
          audioPayload = await uploadParentReasonAudio(wx, app.globalData.serverUrl, {
            filePath: currentJob.voiceFilePath,
          });
          childReasonAudioUrl = String(audioPayload.audioUrl || '').trim();
        }

        payload = await submitParentWrongQuestion(wx, app.globalData.serverUrl, {
          openId: session.openId,
          bindingId: this.data.binding.id,
          filePath: croppedPath,
          childReasonText: String(currentJob.childRawReasonText || '').trim(),
          childReasonInputMode: currentJob.childReasonInputMode,
          childReasonAudioUrl,
        });
        successTaskIds.push((payload.task && payload.task.id) || '');
      }

      this.setData({
        successTaskIds,
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
      wx.showToast({ title: '上传成功', icon: 'success' });
    } catch (error) {
      this.setData({
        errorMessage: error instanceof Error ? error.message : '上传失败',
      });
    } finally {
      this.setData({ submitting: false });
    }
  },

  backHome() {
    wx.reLaunch({ url: '/pages/parent-home/index' });
  },
});
