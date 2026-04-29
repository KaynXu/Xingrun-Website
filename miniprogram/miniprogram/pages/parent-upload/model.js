let imageCounter = 0;
let boxCounter = 0;
const DEFAULT_TOPIC_CATEGORY = '未分类';

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
      childReasonInputMode: String(box.childReasonInputMode || 'text').trim() || 'text',
      topicCategory: String(box.topicCategory || DEFAULT_TOPIC_CATEGORY).trim() || DEFAULT_TOPIC_CATEGORY,
      voiceFilePath: String(box.voiceFilePath || '').trim(),
    })));
  }, []);
}

function buildUploadTaskSummary(tasks) {
  const list = Array.isArray(tasks) ? tasks : [];
  const readyCount = list.filter((task) => String(task.status || '') === 'ready').length;
  const failedTasks = list.filter((task) => String(task.status || '') === 'failed');
  const failedCount = failedTasks.length;
  const pendingCount = Math.max(0, list.length - readyCount - failedCount);

  if (failedCount) {
    const message = String(failedTasks[0].error_message || failedTasks[0].errorMessage || '请重新拍清楚一点').trim();
    return {
      state: 'failed',
      title: '识别失败',
      description: `${failedCount} 条识别失败：${message}`,
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
    description: `已完成 ${readyCount} 条，还有 ${pendingCount} 条正在服务器识别。`,
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
      width: Math.max(0.08, Math.min(1, Number(box.height) || 0)),
      height: Math.max(0.08, Math.min(1, Number(box.width) || 0)),
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
  buildUploadTaskSummary,
  getSubmitBlockers,
  buildUploadJobs,
  rotateImageBoxesClockwise,
};
