const assert = require('node:assert/strict');
const test = require('node:test');

const {
  bindParentStudent,
  cacheParentBinding,
  classifyParentReason,
  ensureParentSession,
  fetchParentBindings,
  fetchChildWrongQuestionLibrary,
  getParentBindings,
  normalizeParentBinding,
  resolveParentEntryPath,
  setParentBindings,
  setParentSession,
  submitParentWrongQuestion,
  transcribeParentReason,
  uploadParentReasonAudio,
  upsertParentBinding,
} = require('./parentApi');

function createWxApi() {
  const storage = new Map();
  return {
    login({ success }) {
      success({ code: 'wx-code-1' });
    },
    request({ url, method, data, success }) {
      if (url.endsWith('/wechat/parent/bindings')) {
        success({
          statusCode: 200,
          data: {
            bindings: [
              {
                id: 21,
                class_id: 8,
                class_name: '六年级 1 班',
                student_id: 101,
                student_name: 'Alice',
                teacher_user_id: 5,
                teacher_name: 'Kayn',
                status: 'active',
              },
            ],
          },
        });
        return;
      }

      if (url.endsWith('/wechat/parent/bind-student')) {
        success({
          statusCode: 200,
          data: {
            binding: {
              id: Number(data.studentId) + 100,
              class_id: data.classId,
              student_id: data.studentId,
              teacher_user_id: 5,
              status: 'active',
            },
          },
        });
        return;
      }

      throw new Error(`Unexpected request: ${method || 'GET'} ${url}`);
    },
    uploadFile({ url, formData, success }) {
      if (url.endsWith('/upload')) {
        success({
          statusCode: 201,
          data: JSON.stringify({
            name: 'voice-reason.mp3',
            url: 'https://example.com/files/voice-reason.mp3',
          }),
        });
        return;
      }

      if (url.endsWith('/wechat/parent/wrong-questions')) {
        success({
          statusCode: 201,
          data: JSON.stringify({
            record: {
              id: 'wechat-record-1',
              binding_id: Number(formData.bindingId),
              source: 'wechat_mp',
            },
          }),
        });
        return;
      }

      throw new Error(`Unexpected upload url: ${url}`);
    },
    getStorageSync(key) {
      return storage.get(key);
    },
    setStorageSync(key, value) {
      storage.set(key, value);
    },
  };
}

test('normalizeParentBinding and upsertParentBinding keep canonical ids for parent-child bindings', () => {
  const first = normalizeParentBinding({
    id: '21',
    class_id: '8',
    class_name: '六年级 1 班',
    student_id: '101',
    student_name: 'Alice',
    teacher_user_id: '5',
    teacher_name: 'Kayn',
  });

  const second = normalizeParentBinding({
    ...first,
    student_name: 'Alice 更新后',
  });

  assert.deepEqual(first, {
    id: 21,
    openId: '',
    classId: 8,
    className: '六年级 1 班',
    studentId: 101,
    studentName: 'Alice',
    teacherUserId: 5,
    teacherName: 'Kayn',
    status: 'active',
  });

  assert.deepEqual(upsertParentBinding([first], second), [second]);
});

test('bindParentStudent caches multiple children and resolveParentEntryPath follows binding presence', async () => {
  const wxApi = createWxApi();
  setParentSession(wxApi, { openId: 'openid-parent-1', accountId: 9 });

  assert.equal(resolveParentEntryPath(wxApi), '/pages/parent-bind/index');

  const firstBinding = await bindParentStudent(wxApi, 'https://example.com', {
    openId: 'openid-parent-1',
    classId: 8,
    className: '六年级 1 班',
    studentId: 101,
    studentName: 'Alice',
    teacherName: 'Kayn',
  });
  const secondBinding = await bindParentStudent(wxApi, 'https://example.com', {
    openId: 'openid-parent-1',
    classId: 8,
    className: '六年级 1 班',
    studentId: 102,
    studentName: 'Bob',
    teacherName: 'Kayn',
  });

  assert.equal(firstBinding.id, 201);
  assert.equal(secondBinding.studentName, 'Bob');
  assert.equal(getParentBindings(wxApi).length, 2);
  assert.equal(resolveParentEntryPath(wxApi), '/pages/parent-home/index');
});

test('fetchParentBindings refreshes cached bindings from the server', async () => {
  const wxApi = createWxApi();
  setParentSession(wxApi, { openId: 'openid-parent-1', accountId: 9 });
  setParentBindings(wxApi, [{
    id: 999,
    classId: 1,
    className: '旧班级',
    studentId: 2,
    studentName: '旧学生',
    teacherUserId: 3,
    teacherName: '旧老师',
  }]);

  const bindings = await fetchParentBindings(wxApi, 'https://example.com', {
    openId: 'openid-parent-1',
  });

  assert.equal(bindings.length, 1);
  assert.equal(bindings[0].id, 21);
  assert.equal(bindings[0].studentName, 'Alice');
  assert.deepEqual(getParentBindings(wxApi), bindings);
});

test('fetchParentBindings rejects when the bindings request never settles', async () => {
  const wxApi = {
    request() {},
    getStorageSync() {
      return undefined;
    },
    setStorageSync() {},
  };

  const outcome = await Promise.race([
    fetchParentBindings(wxApi, 'https://example.com', {
      openId: 'openid-parent-1',
      requestTimeoutMs: 20,
    }).then(
      () => 'resolved',
      (error) => error.message,
    ),
    new Promise((resolve) => setTimeout(() => resolve('pending'), 80)),
  ]);

  assert.equal(outcome, '请求超时，请检查网络后重试');
});

test('ensureParentSession rejects when wx.login never settles', async () => {
  const wxApi = {
    login() {},
    getStorageSync() {
      return undefined;
    },
    setStorageSync() {},
  };

  const outcome = await Promise.race([
    ensureParentSession(wxApi, 'https://example.com', {
      loginTimeoutMs: 20,
    }).then(
      () => 'resolved',
      (error) => error.message,
    ),
    new Promise((resolve) => setTimeout(() => resolve('pending'), 80)),
  ]);

  assert.equal(outcome, '微信登录超时，请检查网络后重试');
});

test('fetchParentBindings maps missing parent routes to a useful error message', async () => {
  const wxApi = {
    request({ success }) {
      success({
        statusCode: 404,
        errMsg: 'request:ok',
        data: '<html><body><pre>Cannot GET /wechat/parent/bindings</pre></body></html>',
      });
    },
    getStorageSync() {
      return undefined;
    },
    setStorageSync() {},
  };

  await assert.rejects(
    () => fetchParentBindings(wxApi, 'https://example.com', { openId: 'openid-parent-1' }),
    {
      message: '家长绑定服务暂未部署，请联系老师稍后再试',
    },
  );
});

test('submitParentWrongQuestion parses the upload bridge response', async () => {
  const wxApi = createWxApi();
  setParentBindings(wxApi, []);
  cacheParentBinding(wxApi, {
    id: 21,
    openId: 'openid-parent-1',
    classId: 8,
    className: '六年级 1 班',
    studentId: 101,
    studentName: 'Alice',
    teacherUserId: 5,
    teacherName: 'Kayn',
  });

  const payload = await submitParentWrongQuestion(wxApi, 'https://example.com', {
    openId: 'openid-parent-1',
    bindingId: 21,
    filePath: '/tmp/mock-image.png',
    childReasonText: '我把乘法顺序看错了',
    childReasonInputMode: 'voice',
    primaryErrorType: '方法问题',
    secondaryErrorSummary: '乘法顺序混淆',
  });

  assert.equal(payload.record.id, 'wechat-record-1');
  assert.equal(payload.record.source, 'wechat_mp');
  assert.equal(payload.record.binding_id, 21);
});

test('submitParentWrongQuestion forwards the child reason text in upload form data', async () => {
  let capturedFormData = null;
  const wxApi = {
    uploadFile({ formData, success }) {
      capturedFormData = formData;
      success({
        statusCode: 201,
        data: JSON.stringify({
          record: {
            id: 'wechat-record-2',
            binding_id: 21,
            source: 'wechat_mp',
          },
        }),
      });
    },
    getStorageSync() {
      return undefined;
    },
    setStorageSync() {},
  };

  await submitParentWrongQuestion(wxApi, 'https://example.com', {
    openId: 'openid-parent-1',
    bindingId: 21,
    filePath: '/tmp/mock-image.png',
    childReasonText: '我把单位换算漏掉了',
    childReasonInputMode: 'text',
    primaryErrorType: '细节问题',
    secondaryErrorSummary: '单位换算遗漏',
  });

  assert.deepEqual(capturedFormData, {
    openId: 'openid-parent-1',
    bindingId: '21',
    childReasonText: '我把单位换算漏掉了',
    childReasonInputMode: 'text',
    primaryErrorType: '细节问题',
    secondaryErrorSummary: '单位换算遗漏',
  });
});

test('uploadParentReasonAudio parses the upload response', async () => {
  const wxApi = createWxApi();

  const payload = await uploadParentReasonAudio(wxApi, 'https://example.com', {
    filePath: '/tmp/mock-audio.mp3',
  });

  assert.deepEqual(payload, {
    audioUrl: 'https://example.com/files/voice-reason.mp3',
    fileName: 'voice-reason.mp3',
  });
});

test('transcribeParentReason posts the uploaded audio url', async () => {
  let capturedRequest = null;
  const wxApi = {
    request({ url, method, data, success }) {
      capturedRequest = { url, method, data };
      success({
        statusCode: 200,
        data: {
          transcript_text: '我把加法看成减法了',
        },
      });
    },
  };

  const payload = await transcribeParentReason(wxApi, 'https://example.com', {
    audioUrl: 'https://example.com/files/voice-reason.mp3',
  });

  assert.deepEqual(capturedRequest, {
    url: 'https://example.com/wechat/parent/reason-transcriptions',
    method: 'POST',
    data: {
      audioUrl: 'https://example.com/files/voice-reason.mp3',
    },
  });
  assert.equal(payload.transcript_text, '我把加法看成减法了');
});

test('classifyParentReason posts the normalized child reason text', async () => {
  let capturedRequest = null;
  const wxApi = {
    request({ url, method, data, success }) {
      capturedRequest = { url, method, data };
      success({
        statusCode: 200,
        data: {
          display_text: '我把单位换算漏掉了',
          primary_error_type: '细节问题',
          secondary_error_summary: '单位换算遗漏',
        },
      });
    },
  };

  const payload = await classifyParentReason(wxApi, 'https://example.com', {
    childReasonText: '  我把单位换算漏掉了  ',
  });

  assert.deepEqual(capturedRequest, {
    url: 'https://example.com/wechat/parent/reason-classifications',
    method: 'POST',
    data: {
      childReasonText: '我把单位换算漏掉了',
    },
  });
  assert.equal(payload.primary_error_type, '细节问题');
});

test('fetchChildWrongQuestionLibrary loads the shared student pdf metadata', async () => {
  let capturedRequest = null;
  const wxApi = {
    request({ url, method, data, success }) {
      capturedRequest = { url, method, data };
      success({
        statusCode: 200,
        data: {
          student_id: 101,
          pdf_url: '/api/wechat/student-libraries/101',
          updated_at: '2026-04-15 12:00:00',
          total_items: 2,
        },
      });
    },
  };

  const payload = await fetchChildWrongQuestionLibrary(wxApi, 'https://example.com', {
    openId: 'openid-parent-1',
    studentId: 101,
  });

  assert.deepEqual(capturedRequest, {
    url: 'https://example.com/wechat/parent/children/101/wrong-question-library',
    method: 'GET',
    data: {
      openId: 'openid-parent-1',
    },
  });
  assert.equal(payload.pdf_url, '/api/wechat/student-libraries/101');
  assert.equal(payload.total_items, 2);
});

test('parentApi no longer exports an AI box detection helper', () => {
  const parentApi = require('./parentApi');

  assert.equal('detectParentWrongQuestionBoxes' in parentApi, false);
});
