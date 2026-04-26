const PARENT_SESSION_KEY = 'xr_parent_session';
const PARENT_BINDINGS_KEY = 'xr_parent_bindings';
const DEFAULT_REQUEST_TIMEOUT_MS = 15000;
const DEFAULT_UPLOAD_TIMEOUT_MS = 30000;
const WRONG_QUESTION_SUBMIT_TIMEOUT_MS = 180000;
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

function requestJson(wxApi, options) {
  const requestOptions = options && typeof options === 'object' ? { ...options } : {};
  const timeoutMs = Number(requestOptions.timeoutMs || 0) > 0
    ? Number(requestOptions.timeoutMs)
    : DEFAULT_REQUEST_TIMEOUT_MS;
  delete requestOptions.timeoutMs;

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

        reject(new Error(extractRequestErrorMessage(response, '请求失败')));
      },
      fail: (error) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        reject(new Error(normalizeAsyncFailureMessage(
          error && error.errMsg,
          '请求失败',
          '请求超时，请检查网络后重试',
        )));
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
  delete uploadOptions.timeoutMs;

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
            reject(new Error(extractRequestErrorMessage(response, '上传返回解析失败')));
            return;
          }
        }

        if (statusCode >= 200 && statusCode < 300) {
          resolve(payload);
          return;
        }

        reject(new Error(extractRequestErrorMessage({
          ...response,
          data: payload,
        }, '上传失败')));
      },
      fail: (error) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timer);
        reject(new Error(normalizeAsyncFailureMessage(
          error && error.errMsg,
          '上传失败',
          '上传超时，请检查网络后重试',
        )));
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
    formData: {
      openId: params.openId,
      bindingId: String(params.bindingId),
      childReasonText: String(params.childReasonText || '').trim(),
      childReasonInputMode: String(params.childReasonInputMode || 'text').trim() || 'text',
      childReasonAudioUrl: String(params.childReasonAudioUrl || '').trim(),
    },
  });
}

async function fetchWrongQuestionUploadTask(wxApi, serverUrl, params) {
  return requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/wrong-question-upload-tasks/${params.taskId}`,
    method: 'GET',
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
};
