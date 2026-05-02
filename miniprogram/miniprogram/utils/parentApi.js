const PARENT_SESSION_KEY = 'xr_parent_session';
const PARENT_BINDINGS_KEY = 'xr_parent_bindings';
const DEFAULT_REQUEST_TIMEOUT_MS = 15000;
const DEFAULT_UPLOAD_TIMEOUT_MS = 30000;
const AUDIO_UPLOAD_TIMEOUT_MS = 20000;
const WRONG_QUESTION_SUBMIT_TIMEOUT_MS = 30000;
const UPLOAD_TASK_STATUS_TIMEOUT_MS = 8000;
const DEFAULT_LOGIN_TIMEOUT_MS = 10000;

function safeGetStorage(wxApi, key, fallbackValue) {
  try {
    const value = wxApi.getStorageSync(key);
    return value === '' || value == null ? fallbackValue : value;
  } catch (_error) {
    return fallbackValue;
  }
}

function safeSetStorage(wxApi, key, value) {
  try {
    wxApi.setStorageSync(key, value);
  } catch (_error) {
    // ignore storage failures for MVP flow
  }
}

function extractRequestErrorMessage(response, fallbackMessage) {
  const payload = response && typeof response === 'object' ? response.data : undefined;
  if (payload && typeof payload === 'object') {
    if (typeof payload.error === 'string' && payload.error.trim()) {
      return payload.error.trim();
    }
    if (typeof payload.message === 'string' && payload.message.trim()) {
      return payload.message.trim();
    }
  }

  const responseText = typeof payload === 'string' ? payload.trim() : '';
  if (
    Number((response && response.statusCode) || 0) === 404
    && /Cannot (GET|POST|PUT|DELETE|PATCH) \/wechat\/parent\//i.test(responseText)
  ) {
    return '家长绑定服务暂未部署，请联系老师稍后再试';
  }

  if (responseText && !/^request:ok$/i.test(responseText)) {
    return responseText;
  }

  const errMsg = String((response && response.errMsg) || '').trim();
  if (errMsg && !/^request:ok$/i.test(errMsg)) {
    return errMsg;
  }

  return fallbackMessage;
}

function createParentApiError(message, metadata) {
  const error = new Error(message);
  const source = metadata && typeof metadata === 'object' ? metadata : {};
  if (source.statusCode !== undefined) {
    error.statusCode = source.statusCode;
  }
  if (source.retryable !== undefined) {
    error.retryable = Boolean(source.retryable);
  }
  return error;
}

function buildHttpError(response, fallbackMessage, messages) {
  const statusCode = Number((response && response.statusCode) || 0);
  const source = messages && typeof messages === 'object' ? messages : {};
  if (statusCode === 413 && source.oversizeMessage) {
    return createParentApiError(source.oversizeMessage, {
      statusCode,
      retryable: false,
    });
  }
  if (statusCode >= 500 && source.serverRetryMessage) {
    return createParentApiError(source.serverRetryMessage, {
      statusCode,
      retryable: true,
    });
  }
  return createParentApiError(extractRequestErrorMessage(response, fallbackMessage), {
    statusCode,
    retryable: statusCode >= 500,
  });
}

function normalizeAsyncFailureMessage(rawMessage, fallbackMessage, timeoutMessage) {
  const message = String(rawMessage || '').trim();
  if (!message) {
    return fallbackMessage;
  }
  if (/timeout/i.test(message)) {
    return timeoutMessage;
  }
  return message;
}

function buildAsyncFailureError(rawMessage, fallbackMessage, messages) {
  const source = messages && typeof messages === 'object' ? messages : {};
  const message = String(rawMessage || '').trim();
  if (/timeout/i.test(message)) {
    return createParentApiError(source.timeoutMessage || fallbackMessage, {
      retryable: true,
    });
  }
  if (/network|interrupted|offline|abort|socket|fail/i.test(message) && source.networkMessage) {
    return createParentApiError(source.networkMessage, {
      retryable: true,
    });
  }
  return createParentApiError(message || fallbackMessage, {
    retryable: false,
  });
}

function requestJson(wxApi, options) {
  const requestOptions = options && typeof options === 'object' ? { ...options } : {};
  const timeoutMs = Number(requestOptions.timeoutMs || 0) > 0
    ? Number(requestOptions.timeoutMs)
    : DEFAULT_REQUEST_TIMEOUT_MS;
  const errorMessages = {
    timeoutMessage: requestOptions.timeoutMessage,
    networkMessage: requestOptions.networkMessage,
    oversizeMessage: requestOptions.oversizeMessage,
    serverRetryMessage: requestOptions.serverRetryMessage,
  };
  delete requestOptions.timeoutMs;
  delete requestOptions.timeoutMessage;
  delete requestOptions.networkMessage;
  delete requestOptions.oversizeMessage;
  delete requestOptions.serverRetryMessage;

  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) {
        return;
      }
      settled = true;
      reject(new Error('请求超时，请检查网络后重试'));
    }, timeoutMs);

    wxApi.request({
      ...requestOptions,
      timeout: Number(requestOptions.timeout || 0) > 0
        ? Number(requestOptions.timeout)
        : timeoutMs,
      success: (response) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        const statusCode = Number(response.statusCode || 0);
        if (statusCode >= 200 && statusCode < 300) {
          resolve(response.data || {});
          return;
        }

        reject(buildHttpError(response, '请求失败', errorMessages));
      },
      fail: (error) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        reject(buildAsyncFailureError(error && error.errMsg, '请求失败', {
          timeoutMessage: errorMessages.timeoutMessage || '请求超时，请检查网络后重试',
          networkMessage: errorMessages.networkMessage,
        }));
      },
    });
  });
}

function ensureLoginCode(wxApi, options = {}) {
  const timeoutMs = Number(options.loginTimeoutMs || 0) > 0
    ? Number(options.loginTimeoutMs)
    : DEFAULT_LOGIN_TIMEOUT_MS;

  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) {
        return;
      }
      settled = true;
      reject(new Error('微信登录超时，请检查网络后重试'));
    }, timeoutMs);

    wxApi.login({
      success: (response) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        if (response.code) {
          resolve(response.code);
          return;
        }
        reject(new Error('微信登录失败'));
      },
      fail: (error) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        reject(new Error(normalizeAsyncFailureMessage(
          error && error.errMsg,
          '微信登录失败',
          '微信登录超时，请检查网络后重试',
        )));
      },
    });
  });
}

function uploadFile(wxApi, options) {
  const uploadOptions = options && typeof options === 'object' ? { ...options } : {};
  const timeoutMs = Number(uploadOptions.timeoutMs || 0) > 0
    ? Number(uploadOptions.timeoutMs)
    : DEFAULT_UPLOAD_TIMEOUT_MS;
  const errorMessages = {
    timeoutMessage: uploadOptions.timeoutMessage,
    networkMessage: uploadOptions.networkMessage,
    oversizeMessage: uploadOptions.oversizeMessage,
    serverRetryMessage: uploadOptions.serverRetryMessage,
  };
  delete uploadOptions.timeoutMs;
  delete uploadOptions.timeoutMessage;
  delete uploadOptions.networkMessage;
  delete uploadOptions.oversizeMessage;
  delete uploadOptions.serverRetryMessage;

  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) {
        return;
      }
      settled = true;
      reject(new Error('上传超时，请检查网络后重试'));
    }, timeoutMs);

    wxApi.uploadFile({
      ...uploadOptions,
      timeout: Number(uploadOptions.timeout || 0) > 0
        ? Number(uploadOptions.timeout)
        : timeoutMs,
      success: (response) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        const statusCode = Number(response.statusCode || 0);
        let payload = {};
        const responseData = response ? response.data : undefined;

        if (responseData && typeof responseData === 'object') {
          payload = responseData;
        } else if (typeof responseData === 'string' && responseData.trim()) {
          try {
            payload = JSON.parse(responseData);
          } catch (_error) {
            reject(createParentApiError(extractRequestErrorMessage(response, '上传返回解析失败'), {
              statusCode,
              retryable: false,
            }));
            return;
          }
        }

        if (statusCode >= 200 && statusCode < 300) {
          resolve(payload);
          return;
        }

        reject(buildHttpError({
          ...response,
          data: payload,
        }, '上传失败', errorMessages));
      },
      fail: (error) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        reject(buildAsyncFailureError(error && error.errMsg, '上传失败', {
          timeoutMessage: errorMessages.timeoutMessage || '上传超时，请检查网络后重试',
          networkMessage: errorMessages.networkMessage,
        }));
      },
    });
  });
}

function normalizeParentSession(session) {
  const source = session && typeof session === 'object' ? session : {};
  return {
    openId: String(source.openId || source.open_id || '').trim(),
    accountId: Number(source.accountId || source.account_id || (source.account && source.account.id) || 0) || 0,
  };
}

function normalizeParentBinding(binding) {
  const source = binding && typeof binding === 'object' ? binding : {};
  return {
    id: Number(source.id || 0) || 0,
    openId: String(source.openId || source.open_id || '').trim(),
    classId: Number(source.classId || source.class_id || 0) || 0,
    className: String(source.className || source.class_name || '').trim(),
    studentId: Number(source.studentId || source.student_id || 0) || 0,
    studentName: String(source.studentName || source.student_name || '').trim(),
    teacherUserId: Number(source.teacherUserId || source.teacher_user_id || 0) || 0,
    teacherName: String(source.teacherName || source.teacher_name || '').trim(),
    status: String(source.status || 'active').trim() || 'active',
  };
}

function getParentSession(wxApi) {
  return normalizeParentSession(safeGetStorage(wxApi, PARENT_SESSION_KEY, {}));
}

function setParentSession(wxApi, session) {
  const normalized = normalizeParentSession(session);
  safeSetStorage(wxApi, PARENT_SESSION_KEY, normalized);
  return normalized;
}

function getParentBindings(wxApi) {
  const items = safeGetStorage(wxApi, PARENT_BINDINGS_KEY, []);
  return Array.isArray(items) ? items.map(normalizeParentBinding).filter((item) => item.id && item.studentId) : [];
}

function setParentBindings(wxApi, bindings) {
  const normalized = Array.isArray(bindings)
    ? bindings.map(normalizeParentBinding).filter((item) => item.id && item.studentId)
    : [];
  safeSetStorage(wxApi, PARENT_BINDINGS_KEY, normalized);
  return normalized;
}

function upsertParentBinding(bindings, binding) {
  const normalized = normalizeParentBinding(binding);
  const list = Array.isArray(bindings) ? bindings.map(normalizeParentBinding) : [];
  const filtered = list.filter((item) => item.id !== normalized.id);
  return [normalized, ...filtered];
}

function cacheParentBinding(wxApi, binding) {
  const bindings = upsertParentBinding(getParentBindings(wxApi), binding);
  return setParentBindings(wxApi, bindings);
}

async function ensureParentSession(wxApi, serverUrl, options = {}) {
  const currentSession = getParentSession(wxApi);
  if (currentSession.openId) {
    return currentSession;
  }

  const code = await ensureLoginCode(wxApi, options);
  const payload = await requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/login`,
    method: 'POST',
    timeoutMs: options.requestTimeoutMs,
    data: {
      code,
      nicknameSnapshot: options.nicknameSnapshot || '',
      avatarUrlSnapshot: options.avatarUrlSnapshot || '',
    },
  });

  return setParentSession(wxApi, {
    openId: payload.openId,
    accountId: (payload.account && payload.account.id) || 0,
  });
}

function resolveParentEntryPath(wxApi) {
  return getParentBindings(wxApi).length > 0
    ? '/pages/parent-home/index'
    : '/pages/parent-bind/index';
}

async function previewClassInvite(wxApi, serverUrl, params) {
  return requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/bind-class`,
    method: 'POST',
    data: {
      openId: params.openId,
      inviteCode: String(params.inviteCode || '').trim(),
    },
  });
}

async function bindParentStudent(wxApi, serverUrl, params) {
  const payload = await requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/bind-student`,
    method: 'POST',
    data: {
      openId: params.openId,
      classId: params.classId,
      studentId: params.studentId,
    },
  });

  const bindingRecord = normalizeParentBinding({
    ...payload.binding,
    openId: params.openId,
    className: params.className,
    studentName: params.studentName,
    teacherName: params.teacherName,
  });

  cacheParentBinding(wxApi, bindingRecord);
  return bindingRecord;
}

async function fetchParentBindings(wxApi, serverUrl, params) {
  const payload = await requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/bindings`,
    method: 'GET',
    timeoutMs: params.requestTimeoutMs,
    data: {
      openId: params.openId,
    },
  });

  return setParentBindings(wxApi, payload.bindings || []);
}

async function transcribeParentReason(wxApi, serverUrl, params) {
  return requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/reason-transcriptions`,
    method: 'POST',
    data: {
      audioUrl: String(params.audioUrl || '').trim(),
    },
  });
}

async function classifyParentReason(wxApi, serverUrl, params) {
  return requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/reason-classifications`,
    method: 'POST',
    data: {
      childReasonText: String(params.childReasonText || '').trim(),
    },
  });
}

async function uploadParentReasonAudio(wxApi, serverUrl, params) {
  const payload = await uploadFile(wxApi, {
    url: `${serverUrl}/upload`,
    filePath: params.filePath,
    name: 'file',
    timeoutMs: AUDIO_UPLOAD_TIMEOUT_MS,
    timeoutMessage: '语音上传超时，录音还在本机，请检查网络后重试。',
    networkMessage: '网络连接中断，录音还在本机，请检查网络后重试。',
    oversizeMessage: '录音文件太大，请重新录一段更短的语音。',
    serverRetryMessage: '服务器暂时没有接住语音，录音还在本机，请稍后重试。',
    formData: {},
  });

  return {
    audioUrl: String(payload.url || '').trim(),
    fileName: String(payload.name || '').trim(),
  };
}

async function submitParentWrongQuestion(wxApi, serverUrl, params) {
  return uploadFile(wxApi, {
    url: `${serverUrl}/wechat/parent/wrong-questions`,
    filePath: params.filePath,
    name: 'file',
    timeoutMs: WRONG_QUESTION_SUBMIT_TIMEOUT_MS,
    timeoutMessage: '题图上传超时，草稿已保留，请检查网络后重试。',
    networkMessage: '网络连接中断，草稿已保留，请检查网络后重试。',
    oversizeMessage: '题图仍然太大，草稿已保留，请缩小框选范围或重新拍清楚一点再试。',
    serverRetryMessage: '服务器暂时没有接住上传，草稿已保留，请稍后点“统一提交所有错题”重试。',
    formData: {
      openId: params.openId,
      bindingId: String(params.bindingId),
      childReasonText: String(params.childReasonText || '').trim(),
      childReasonInputMode: String(params.childReasonInputMode || 'text').trim() || 'text',
      childReasonAudioUrl: String(params.childReasonAudioUrl || '').trim(),
      topicCategory: String(params.topicCategory || '未分类').trim() || '未分类',
    },
  });
}

async function fetchWrongQuestionUploadTask(wxApi, serverUrl, params) {
  return requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/wrong-question-upload-tasks/${params.taskId}`,
    method: 'GET',
    timeoutMs: UPLOAD_TASK_STATUS_TIMEOUT_MS,
    timeoutMessage: '刷新上传进度超时，已接收的任务仍会继续处理，请稍后再看。',
    networkMessage: '刷新上传进度失败，已接收的任务仍会继续处理，请稍后再看。',
    data: {
      openId: params.openId,
    },
  });
}

async function fetchChildWrongQuestions(wxApi, serverUrl, params) {
  return requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/children/${params.studentId}/wrong-questions`,
    method: 'GET',
    data: {
      openId: params.openId,
    },
  });
}

async function fetchChildWrongQuestionLibrary(wxApi, serverUrl, params) {
  return requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/children/${params.studentId}/wrong-question-library`,
    method: 'GET',
    data: {
      openId: params.openId,
    },
  });
}

async function updateChildWrongQuestionTopicCategory(wxApi, serverUrl, params) {
  return requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/wrong-questions/${params.recordId}/topic-category`,
    method: 'PUT',
    data: {
      openId: params.openId,
      topicCategory: String(params.topicCategory || '未分类').trim() || '未分类',
    },
  });
}

module.exports = {
  PARENT_SESSION_KEY,
  PARENT_BINDINGS_KEY,
  normalizeParentSession,
  normalizeParentBinding,
  getParentSession,
  setParentSession,
  getParentBindings,
  setParentBindings,
  upsertParentBinding,
  cacheParentBinding,
  ensureParentSession,
  resolveParentEntryPath,
  previewClassInvite,
  bindParentStudent,
  fetchParentBindings,
  transcribeParentReason,
  classifyParentReason,
  uploadParentReasonAudio,
  submitParentWrongQuestion,
  fetchWrongQuestionUploadTask,
  fetchChildWrongQuestions,
  fetchChildWrongQuestionLibrary,
  updateChildWrongQuestionTopicCategory,
};
