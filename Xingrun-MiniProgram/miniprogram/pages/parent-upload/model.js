let imageCounter = 0;
let boxCounter = 0;

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

function appendLocalImages(imageItems, filePaths) {
  const list = Array.isArray(imageItems) ? imageItems.slice() : [];
  const nextPaths = Array.isArray(filePaths) ? filePaths : [];
  return list.concat(nextPaths.map((localPath) => {
    imageCounter += 1;
    return {
      id: `img_${imageCounter}`,
      localPath,
      aiStatus: 'idle',
      aiErrorMessage: '',
      boxes: [],
      activeBoxId: '',
    };
  }));
}

function applyAiBoxesToImage(imageItem, boxes) {
  const nextBoxes = Array.isArray(boxes)
    ? boxes.map((box) => ({ ...createDefaultBox('ai'), ...box, source: 'ai', childReasonText: String(box.childReasonText || '') }))
    : [];
  return {
    ...imageItem,
    aiStatus: nextBoxes.length > 0 ? 'done' : 'empty',
    aiErrorMessage: '',
    boxes: nextBoxes,
    activeBoxId: nextBoxes[0] ? nextBoxes[0].id : '',
  };
}

function addManualBoxToImage(imageItem) {
  const box = createDefaultBox('manual');
  return {
    ...imageItem,
    aiStatus: imageItem.aiStatus === 'empty' ? 'done' : imageItem.aiStatus,
    boxes: (imageItem.boxes || []).concat(box),
    activeBoxId: box.id,
  };
}

function getSubmitBlockers(imageItems) {
  const list = Array.isArray(imageItems) ? imageItems : [];
  const missingReasonBoxIds = [];

  list.forEach((item) => {
    (item.boxes || []).forEach((box) => {
      if (String(box.childReasonInputMode || 'text') === 'voice') {
        if (!String(box.voiceFilePath || '').trim()) {
          missingReasonBoxIds.push(box.id);
        }
        return;
      }

      if (!String(box.childReasonText || '').trim()) {
        missingReasonBoxIds.push(box.id);
      }
    });
  });

  return {
    emptyImageIds: list.filter((item) => !(item.boxes || []).length).map((item) => item.id),
    runningImageIds: list.filter((item) => item.aiStatus === 'running').map((item) => item.id),
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
      voiceFilePath: String(box.voiceFilePath || '').trim(),
    })));
  }, []);
}

function rotateImageBoxesClockwise(imageItem) {
  if (!imageItem) {
    return imageItem;
  }

  return {
    ...imageItem,
    boxes: (imageItem.boxes || []).map((box) => {
      return {
        ...box,
        x: Math.max(0, Math.min(1, 1 - (Number(box.y) || 0) - (Number(box.height) || 0))),
        y: Math.max(0, Math.min(1, Number(box.x) || 0)),
        width: Math.max(0.08, Math.min(1, Number(box.height) || 0)),
        height: Math.max(0.08, Math.min(1, Number(box.width) || 0)),
      };
    }),
  };
}

module.exports = {
  appendLocalImages,
  applyAiBoxesToImage,
  addManualBoxToImage,
  buildImageRotationPlan,
  getSubmitBlockers,
  buildUploadJobs,
  rotateImageBoxesClockwise,
};
