let imageCounter = 0;
let boxCounter = 0;
const DEFAULT_TOPIC_CATEGORY = '未分类';
const MIN_CROP_BOX_DISPLAY_SIZE = 16;
const MIN_CROP_BOX_RATIO = 0.01;

function toFiniteNumber(value, fallbackValue) {
  const numberValue = Number(value);
  return isFinite(numberValue) ? numberValue : fallbackValue;
}

function clampNumber(value, minValue, maxValue) {
  return Math.max(minValue, Math.min(value, maxValue));
}

function resolveMinCropBoxDisplaySize(value) {
  const minSize = Math.round(toFiniteNumber(value, MIN_CROP_BOX_DISPLAY_SIZE));
  return Math.max(1, minSize || MIN_CROP_BOX_DISPLAY_SIZE);
}

function normalizeQuarterTurns(value) {
  const turns = Math.round(Number(value) || 0);
  return ((turns % 4) + 4) % 4;
}

function createDefaultBox(source) {
  boxCounter += 1;
  return {
    id: `box_${boxCounter}`,
    source,
    x: 0.15,
    y: 0.18,
    width: 0.7,
    height: 0.28,
    childReasonText: '',
    childReasonInputMode: 'text',
    topicCategory: DEFAULT_TOPIC_CATEGORY,
    voiceFilePath: '',
    voiceFileName: '',
    reasonStatusText: '',
  };
}

function buildImageRotationPlan(options) {
  const width = Math.max(1, Math.round(Number(options && options.width) || 0));
  const height = Math.max(1, Math.round(Number(options && options.height) || 0));
  const quarterTurns = normalizeQuarterTurns(options && options.quarterTurns);

  if (quarterTurns === 1) {
    return {
      canvasWidth: height,
      canvasHeight: width,
      translateX: height,
      translateY: 0,
      rotationRadians: Math.PI / 2,
      backgroundColor: '#ffffff',
    };
  }

  if (quarterTurns === 2) {
    return {
      canvasWidth: width,
      canvasHeight: height,
      translateX: width,
      translateY: height,
      rotationRadians: Math.PI,
      backgroundColor: '#ffffff',
    };
  }

  if (quarterTurns === 3) {
    return {
      canvasWidth: height,
      canvasHeight: width,
      translateX: 0,
      translateY: width,
      rotationRadians: Math.PI * 1.5,
      backgroundColor: '#ffffff',
    };
  }

  return {
    canvasWidth: width,
    canvasHeight: height,
    translateX: 0,
    translateY: 0,
    rotationRadians: 0,
    backgroundColor: '#ffffff',
  };
}

function buildUploadExportPlan(options) {
  const cropWidth = Math.max(1, Math.round(Number(options && options.cropWidth) || 0));
  const cropHeight = Math.max(1, Math.round(Number(options && options.cropHeight) || 0));
  const maxLongEdge = 1792;
  const maxShortEdge = 1280;
  const scale = Math.min(
    1,
    maxLongEdge / Math.max(cropWidth, cropHeight),
    maxShortEdge / Math.min(cropWidth, cropHeight)
  );

  return {
    outputWidth: Math.max(1, Math.round(cropWidth * scale)),
    outputHeight: Math.max(1, Math.round(cropHeight * scale)),
    quality: 0.82,
  };
}

function buildBoxTouchFrame(options) {
  const source = options || {};
  const mode = String(source.mode || 'move');
  const minSize = resolveMinCropBoxDisplaySize(source.minSize);
  const imageLeft = toFiniteNumber(source.imageLeft, 0);
  const imageTop = toFiniteNumber(source.imageTop, 0);
  const imageWidth = Math.max(1, toFiniteNumber(source.imageWidth, 1));
  const imageHeight = Math.max(1, toFiniteNumber(source.imageHeight, 1));
  const imageRight = imageLeft + imageWidth;
  const imageBottom = imageTop + imageHeight;
  const deltaX = toFiniteNumber(source.deltaX, 0);
  const deltaY = toFiniteNumber(source.deltaY, 0);

  let nextLeft = toFiniteNumber(source.startLeft, imageLeft);
  let nextTop = toFiniteNumber(source.startTop, imageTop);
  let nextWidth = toFiniteNumber(source.startWidth, minSize);
  let nextHeight = toFiniteNumber(source.startHeight, minSize);

  if (mode === 'move') {
    nextLeft = clampNumber(nextLeft + deltaX, imageLeft, imageRight - nextWidth);
    nextTop = clampNumber(nextTop + deltaY, imageTop, imageBottom - nextHeight);
  } else if (mode === 'resize-se') {
    nextWidth = Math.max(minSize, Math.min(nextWidth + deltaX, imageRight - nextLeft));
    nextHeight = Math.max(minSize, Math.min(nextHeight + deltaY, imageBottom - nextTop));
  } else if (mode === 'resize-sw') {
    const right = nextLeft + nextWidth;
    nextLeft = clampNumber(nextLeft + deltaX, imageLeft, right - minSize);
    nextWidth = right - nextLeft;
    nextHeight = Math.max(minSize, Math.min(nextHeight + deltaY, imageBottom - nextTop));
  } else if (mode === 'resize-ne') {
    const bottom = nextTop + nextHeight;
    nextTop = clampNumber(nextTop + deltaY, imageTop, bottom - minSize);
    nextHeight = bottom - nextTop;
    nextWidth = Math.max(minSize, Math.min(nextWidth + deltaX, imageRight - nextLeft));
  } else if (mode === 'resize-nw') {
    const right = nextLeft + nextWidth;
    const bottom = nextTop + nextHeight;
    nextLeft = clampNumber(nextLeft + deltaX, imageLeft, right - minSize);
    nextTop = clampNumber(nextTop + deltaY, imageTop, bottom - minSize);
    nextWidth = right - nextLeft;
    nextHeight = bottom - nextTop;
  }

  return {
    left: nextLeft,
    top: nextTop,
    width: nextWidth,
    height: nextHeight,
  };
}

function normalizeDisplayBoxFrame(options) {
  const source = options || {};
  const minSize = resolveMinCropBoxDisplaySize(source.minSize);
  const imageLeft = toFiniteNumber(source.imageLeft, 0);
  const imageTop = toFiniteNumber(source.imageTop, 0);
  const imageWidth = Math.max(1, toFiniteNumber(source.imageWidth, 1));
  const imageHeight = Math.max(1, toFiniteNumber(source.imageHeight, 1));
  const width = Math.max(Math.min(minSize, imageWidth), Math.min(toFiniteNumber(source.width, minSize), imageWidth));
  const height = Math.max(Math.min(minSize, imageHeight), Math.min(toFiniteNumber(source.height, minSize), imageHeight));
  const left = clampNumber(toFiniteNumber(source.left, imageLeft), imageLeft, imageLeft + imageWidth - width);
  const top = clampNumber(toFiniteNumber(source.top, imageTop), imageTop, imageTop + imageHeight - height);

  return {
    x: (left - imageLeft) / imageWidth,
    y: (top - imageTop) / imageHeight,
    width: width / imageWidth,
    height: height / imageHeight,
  };
}

function appendLocalImages(imageItems, filePaths) {
  const list = Array.isArray(imageItems) ? imageItems.slice() : [];
  const nextPaths = Array.isArray(filePaths) ? filePaths : [];
  return list.concat(nextPaths.map((localPath) => {
    imageCounter += 1;
    return {
      id: `img_${imageCounter}`,
      localPath,
      contentVersion: 0,
      boxes: [],
      activeBoxId: '',
    };
  }));
}

function addManualBoxToImage(imageItem) {
  const box = createDefaultBox('manual');
  return {
    ...imageItem,
    boxes: (imageItem.boxes || []).concat(box),
    activeBoxId: box.id,
  };
}

function getSubmitBlockers(imageItems) {
  const list = Array.isArray(imageItems) ? imageItems : [];
  const missingReasonBoxIds = [];

  return {
    emptyImageIds: list.filter((item) => !(item.boxes || []).length).map((item) => item.id),
    missingReasonBoxIds,
  };
}

function buildUploadJobs(imageItems) {
  const list = Array.isArray(imageItems) ? imageItems : [];
  return list.reduce((jobs, item) => {
    return jobs.concat((item.boxes || []).map((box) => ({
      imageId: item.id,
      boxId: box.id,
      localPath: item.localPath,
      box,
      childRawReasonText: String(box.childReasonText || '').trim(),
      childReasonInputMode: String(box.childReasonInputMode || 'text').trim() === 'voice' && String(box.voiceFilePath || '').trim()
        ? 'voice'
        : 'text',
      topicCategory: String(box.topicCategory || DEFAULT_TOPIC_CATEGORY).trim() || DEFAULT_TOPIC_CATEGORY,
      voiceFilePath: String(box.voiceFilePath || '').trim(),
    })));
  }, []);
}

function getUploadTaskStatus(task) {
  const source = task && typeof task === 'object' ? task : {};
  const state = String(source.state || '').trim();
  if (state === 'missing_record') {
    return 'processing';
  }
  if (state === 'pending' || state === 'processing' || state === 'ready' || state === 'failed') {
    return state;
  }
  return String(source.status || '').trim();
}

function isMissingRecordUploadTask(task) {
  const source = task && typeof task === 'object' ? task : {};
  return String(source.state || '').trim() === 'missing_record'
    || source.record_missing === true
    || source.recordMissing === true;
}

function isStaleUploadTask(task) {
  const source = task && typeof task === 'object' ? task : {};
  const status = getUploadTaskStatus(source);
  return (source.is_stale === true || source.isStale === true)
    && status !== 'ready'
    && status !== 'failed';
}

function buildUploadTaskSummary(tasks, options) {
  const list = Array.isArray(tasks) ? tasks : [];
  const readyCount = list.filter((task) => getUploadTaskStatus(task) === 'ready' && !isMissingRecordUploadTask(task)).length;
  const failedTasks = list.filter((task) => getUploadTaskStatus(task) === 'failed');
  const failedCount = failedTasks.length;
  const pendingCount = Math.max(0, list.length - readyCount - failedCount);
  const missingRecordCount = list.filter(isMissingRecordUploadTask).length;
  const staleCount = list.filter(isStaleUploadTask).length;

  if (failedCount) {
    const message = String(
      failedTasks[0].parent_error_message
      || failedTasks[0].parentErrorMessage
      || failedTasks[0].error_message
      || failedTasks[0].errorMessage
      || '请重新拍清楚一点',
    ).trim();
    const hasAcceptedItems = readyCount > 0 || pendingCount > 0;
    let pendingMessage = '';
    if (pendingCount) {
      if (missingRecordCount) {
        pendingMessage = `；${missingRecordCount} 条错题记录暂时还没有同步出来`;
      } else if (staleCount) {
        pendingMessage = `；${pendingCount} 条还在云端处理，时间比平时久，可以稍后回错题本刷新`;
      } else {
        pendingMessage = `；${pendingCount} 条还在${options && options.background ? '云端继续识别，可以先离开本页，稍后回错题本查看' : '云端继续识别'}`;
      }
    }
    return {
      state: hasAcceptedItems ? 'partial_failed' : 'failed',
      title: hasAcceptedItems ? '部分识别失败' : '识别失败',
      description: `${failedCount} 条识别失败：${message}${pendingMessage}`,
      readyCount,
      failedCount,
      pendingCount,
    };
  }

  if (missingRecordCount) {
    return {
      state: options && options.background ? 'background' : 'pending',
      title: options && options.background ? '错题记录同步中' : '正在同步错题记录',
      description: `${missingRecordCount} 条上传已接收，但错题记录暂时还没有同步出来。请稍后刷新错题本，任务不会丢失。`,
      readyCount,
      failedCount,
      pendingCount,
    };
  }

  if (options && options.background && staleCount) {
    return {
      state: 'background',
      title: '云端处理时间较长',
      description: `${staleCount} 条上传已接收，但云端处理时间比平时久。任务不会丢失，可以稍后回错题本刷新。`,
      readyCount,
      failedCount,
      pendingCount,
    };
  }

  if (options && options.background && pendingCount) {
    return {
      state: 'background',
      title: '已接收，云端识别中',
      description: `已完成 ${readyCount} 条，还有 ${pendingCount} 条在云端继续识别。可以先离开本页，稍后回错题本查看。`,
      readyCount,
      failedCount,
      pendingCount,
    };
  }

  if (list.length && readyCount === list.length) {
    return {
      state: 'ready',
      title: '识别完成',
      description: `本次 ${readyCount} 条错题已加入错题本。`,
      readyCount,
      failedCount,
      pendingCount,
    };
  }

  return {
    state: 'pending',
    title: '正在识别',
    description: `已完成 ${readyCount} 条，还有 ${pendingCount} 条正在云端识别。`,
    readyCount,
    failedCount,
    pendingCount,
  };
}

function rotateImageBoxesClockwise(imageItem) {
  if (!imageItem) {
    return imageItem;
  }

  const nextBoxes = (imageItem.boxes || []).map((box) => {
    return {
      ...box,
      x: Math.max(0, Math.min(1, 1 - (Number(box.y) || 0) - (Number(box.height) || 0))),
      y: Math.max(0, Math.min(1, Number(box.x) || 0)),
      width: Math.max(MIN_CROP_BOX_RATIO, Math.min(1, Number(box.height) || 0)),
      height: Math.max(MIN_CROP_BOX_RATIO, Math.min(1, Number(box.width) || 0)),
    };
  });

  return {
    ...imageItem,
    contentVersion: (Number(imageItem.contentVersion) || 0) + 1,
    boxes: nextBoxes,
  };
}

module.exports = {
  appendLocalImages,
  addManualBoxToImage,
  buildUploadExportPlan,
  buildImageRotationPlan,
  buildBoxTouchFrame,
  buildUploadTaskSummary,
  getSubmitBlockers,
  buildUploadJobs,
  normalizeDisplayBoxFrame,
  rotateImageBoxesClockwise,
};
