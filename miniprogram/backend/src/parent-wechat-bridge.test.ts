import assert from 'node:assert/strict';
import { once } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UPLOADS_DIR = path.resolve(__dirname, '../../uploads');
const LEGACY_UPLOADS_DIR = path.resolve(__dirname, '../../legacy-uploads-test');

async function loadAppModule() {
  process.env.WEBSITE_API_BASE_URL = 'https://website.example';
  process.env.WEBSITE_API_TOKEN = 'wechat-service-token';
  process.env.LEGACY_UPLOADS_DIRS = LEGACY_UPLOADS_DIR;
  return import('./index.js');
}

async function startTestServer(t: test.TestContext) {
  const { createApp } = await loadAppModule();
  const app = createApp();
  const server = app.listen(0);
  t.after(() => {
    server.close();
  });

  await once(server, 'listening');
  const address = server.address();
  assert.ok(address && typeof address === 'object');
  return server;
}

function createJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json',
    },
  });
}

function createParentUploadForm() {
  const formData = new FormData();
  formData.set('openId', 'openid-parent-1');
  formData.set('bindingId', '21');
  formData.set('file', new Blob(['mock-image']), 'wrong-question.txt');
  return formData;
}

function trackUploadedFileFromImageUrl(uploadedFiles: string[], imageUrl: unknown) {
  const fileName = String(imageUrl || '').split('/files/')[1] || '';
  if (fileName) {
    uploadedFiles.push(fileName);
  }
}

test('parent login and binding bridge forward canonical payloads to the website', async (t) => {
  const originalFetch = globalThis.fetch;
  const websiteCalls: Array<{ url: string; init?: RequestInit }> = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url.startsWith('https://website.example')) {
      websiteCalls.push({ url, init });

      if (url.endsWith('/api/wechat/login')) {
        return createJsonResponse({
          account: {
            id: 11,
            openid: 'openid-parent-1',
          },
        });
      }

      if (url.endsWith('/api/wechat/bind-class')) {
        return createJsonResponse({
          class_id: 8,
          class_name: '六年级 1 班',
          students: [
            { id: 101, name: 'Alice' },
            { id: 102, name: 'Bob' },
          ],
        });
      }

      if (url.endsWith('/api/wechat/bind-student')) {
        return createJsonResponse({
          binding: {
            id: 21,
            class_id: 8,
            student_id: 101,
            teacher_user_id: 5,
            status: 'active',
          },
        });
      }
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const loginResponse = await fetch(`${baseUrl}/wechat/parent/login`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        openId: 'openid-parent-1',
        nicknameSnapshot: 'Alice 妈妈',
      }),
    });
    assert.equal(loginResponse.status, 200);
    assert.equal((await loginResponse.json()).openId, 'openid-parent-1');

    const previewResponse = await fetch(`${baseUrl}/wechat/parent/bind-class`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        openId: 'openid-parent-1',
        inviteCode: 'AB12CD',
      }),
    });
    assert.equal(previewResponse.status, 200);
    assert.equal((await previewResponse.json()).students[0].name, 'Alice');

    const bindResponse = await fetch(`${baseUrl}/wechat/parent/bind-student`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        openId: 'openid-parent-1',
        classId: 8,
        studentId: 101,
      }),
    });
    assert.equal(bindResponse.status, 200);
    assert.equal((await bindResponse.json()).binding.id, 21);

    assert.equal(websiteCalls.length, 3);
    assert.equal(websiteCalls[0]?.url, 'https://website.example/api/wechat/login');
    assert.equal(websiteCalls[1]?.url, 'https://website.example/api/wechat/bind-class');
    assert.equal(websiteCalls[2]?.url, 'https://website.example/api/wechat/bind-student');
    const bindClassBody = JSON.parse(String(websiteCalls[1]?.init?.body || '{}'));
    const bindStudentBody = JSON.parse(String(websiteCalls[2]?.init?.body || '{}'));
    assert.equal(bindClassBody.open_id, 'openid-parent-1');
    assert.equal(bindClassBody.invite_code, 'AB12CD');
    assert.equal(bindStudentBody.class_id, 8);
    assert.equal(bindStudentBody.student_id, 101);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent bindings bridge forwards the canonical openid to the website and returns fresh bindings', async (t) => {
  const originalFetch = globalThis.fetch;
  const websiteCalls: Array<{ url: string; init?: RequestInit }> = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url.startsWith('https://website.example')) {
      websiteCalls.push({ url, init });
      if (url.includes('/api/wechat/bindings?')) {
        return createJsonResponse({
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
        });
      }
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/bindings?openId=openid-parent-1`);

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.bindings.length, 1);
    assert.equal(payload.bindings[0].student_name, 'Alice');
    assert.equal(websiteCalls.length, 1);
    assert.equal(websiteCalls[0]?.url, 'https://website.example/api/wechat/bindings?open_id=openid-parent-1');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent wrong-question-library bridge forwards the canonical openid to the website', async (t) => {
  const originalFetch = globalThis.fetch;
  const websiteCalls: Array<{ url: string; init?: RequestInit }> = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url.startsWith('https://website.example')) {
      websiteCalls.push({ url, init });
      if (url.includes('/api/wechat/children/101/wrong-question-library?')) {
        return createJsonResponse({
          student_id: 101,
          pdf_url: '/api/wechat/student-libraries/101',
          updated_at: '2026-04-15 12:00:00',
          total_items: 2,
        });
      }
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/children/101/wrong-question-library?openId=openid-parent-1`);

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.pdf_url, '/api/wechat/student-libraries/101');
    assert.equal(payload.total_items, 2);
    assert.equal(websiteCalls.length, 1);
    assert.equal(websiteCalls[0]?.url, 'https://website.example/api/wechat/children/101/wrong-question-library?open_id=openid-parent-1');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent topic category bridge forwards parent edits to the website', async (t) => {
  const originalFetch = globalThis.fetch;
  const websiteCalls: Array<{ url: string; init?: RequestInit }> = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-questions/wechat-record-1/topic-category') {
      websiteCalls.push({ url, init });
      const body = JSON.parse(String(init?.body || '{}'));
      assert.equal(body.open_id, 'openid-parent-1');
      assert.equal(body.topic_category, '周期问题');
      return createJsonResponse({
        ok: true,
        record: {
          id: 'wechat-record-1',
          topic_category: '周期问题',
        },
      });
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions/wechat-record-1/topic-category`, {
      method: 'PUT',
      headers: {
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        openId: 'openid-parent-1',
        topicCategory: '周期问题',
      }),
    });

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.record.topic_category, '周期问题');
    assert.equal(websiteCalls.length, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent topic category suggestions bridge forwards parent openid to the website', async (t) => {
  const originalFetch = globalThis.fetch;
  const websiteCalls: Array<{ url: string; init?: RequestInit }> = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url.startsWith('https://website.example')) {
      websiteCalls.push({ url, init });
      if (url.includes('/api/wechat/primary-topic-category-suggestions?')) {
        return createJsonResponse({
          items: ['周期问题', '几何模型'],
        });
      }
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/primary-topic-category-suggestions?openId=openid-parent-1&topicCategory=%E5%91%A8%E6%9C%9F`);

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.deepEqual(payload.items, ['周期问题', '几何模型']);
    assert.equal(websiteCalls.length, 1);
    assert.equal(websiteCalls[0]?.url, 'https://website.example/api/wechat/primary-topic-category-suggestions?open_id=openid-parent-1&topic_category=%E5%91%A8%E6%9C%9F');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent upload bridge stores the file locally and forwards the generated image url to the website', async (t) => {
  const originalFetch = globalThis.fetch;
  const uploadedFiles: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-questions') {
      const body = JSON.parse(String(init?.body || '{}'));
      assert.equal(body.open_id, 'openid-parent-1');
      assert.equal(body.binding_id, 21);
      assert.equal(body.child_raw_reason_text, '我把单位换算漏掉了');
      assert.equal(body.child_reason_input_mode, 'voice');
      assert.equal(body.child_reason_audio_url, 'https://example.com/files/reason.m4a');
      assert.equal(body.topic_category, '周期问题');
      assert.match(body.image_url, /^http:\/\/127\.0\.0\.1:\d+\/files\/.+/);

      const fileName = String(body.image_url).split('/files/')[1];
      uploadedFiles.push(fileName);

      return createJsonResponse({
        task: {
          id: 9001,
          binding_id: 21,
          student_id: 101,
          status: 'pending',
          image_url: body.image_url,
        },
      }, 202);
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;
    const formData = new FormData();
    formData.set('openId', 'openid-parent-1');
    formData.set('bindingId', '21');
    formData.set('childReasonText', '我把单位换算漏掉了');
    formData.set('childReasonInputMode', 'voice');
    formData.set('childReasonAudioUrl', 'https://example.com/files/reason.m4a');
    formData.set('topicCategory', '周期问题');
    formData.set('file', new Blob(['mock-image']), 'wrong-question.txt');

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions`, {
      method: 'POST',
      body: formData,
    });

    assert.equal(response.status, 202);
    const payload = await response.json();
    assert.equal(payload.task.id, 9001);
    assert.equal(payload.task.status, 'pending');

    const uploadedPath = uploadedFiles[0] ? path.join(UPLOADS_DIR, uploadedFiles[0]) : '';
    assert.ok(uploadedPath);
    assert.equal(fs.existsSync(uploadedPath), true);

    t.after(() => {
      if (uploadedPath) {
        fs.rmSync(uploadedPath, { force: true });
      }
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent upload bridge allows image-only submissions for server-side recognition', async (t) => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-questions') {
      const body = JSON.parse(String(init?.body || '{}'));
      assert.equal(body.child_raw_reason_text, '');
      assert.equal(body.child_reason_audio_url, '');
      assert.match(body.image_url, /^http:\/\/127\.0\.0\.1:\d+\/files\/.+/);

      return createJsonResponse({
        task: {
          id: 9002,
          status: 'pending',
          image_url: body.image_url,
        },
      }, 202);
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;
    const formData = new FormData();
    formData.set('openId', 'openid-parent-1');
    formData.set('bindingId', '21');
    formData.set('file', new Blob(['mock-image']), 'wrong-question.txt');

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions`, {
      method: 'POST',
      body: formData,
    });

    assert.equal(response.status, 202);
    assert.equal((await response.json()).task.id, 9002);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent upload bridge preserves website accepted task payloads with optional fields missing', async (t) => {
  const originalFetch = globalThis.fetch;
  const uploadedFiles: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-questions') {
      const body = JSON.parse(String(init?.body || '{}'));
      trackUploadedFileFromImageUrl(uploadedFiles, body.image_url);
      return createJsonResponse({
        task: {
          id: 9101,
          status: 'pending',
        },
        retryable: false,
      }, 202);
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions`, {
      method: 'POST',
      body: createParentUploadForm(),
    });

    assert.equal(response.status, 202);
    const payload = await response.json();
    assert.deepEqual(payload, {
      task: {
        id: 9101,
        status: 'pending',
      },
      retryable: false,
    });
  } finally {
    globalThis.fetch = originalFetch;
    for (const fileName of uploadedFiles) {
      fs.rmSync(path.join(UPLOADS_DIR, fileName), { force: true });
    }
  }
});

test('parent upload bridge maps website validation failures without losing structured fields', async (t) => {
  const originalFetch = globalThis.fetch;
  const uploadedFiles: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-questions') {
      const body = JSON.parse(String(init?.body || '{}'));
      trackUploadedFileFromImageUrl(uploadedFiles, body.image_url);
      return createJsonResponse({
        error: '绑定关系已失效，请重新绑定孩子',
        retryable: false,
        task: {
          id: 9102,
          status: 'failed',
          error_message: 'binding inactive',
        },
      }, 400);
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions`, {
      method: 'POST',
      body: createParentUploadForm(),
    });

    assert.equal(response.status, 400);
    const payload = await response.json();
    assert.equal(payload.error, '绑定关系已失效，请重新绑定孩子');
    assert.equal(payload.retryable, false);
    assert.equal(payload.task.id, 9102);
  } finally {
    globalThis.fetch = originalFetch;
    for (const fileName of uploadedFiles) {
      fs.rmSync(path.join(UPLOADS_DIR, fileName), { force: true });
    }
  }
});

test('parent upload bridge maps website payload-too-large failures as final', async (t) => {
  const originalFetch = globalThis.fetch;
  const uploadedFiles: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-questions') {
      const body = JSON.parse(String(init?.body || '{}'));
      trackUploadedFileFromImageUrl(uploadedFiles, body.image_url);
      return createJsonResponse({
        error: '题图文件太大，请缩小框选范围后重试',
        retryable: false,
      }, 413);
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions`, {
      method: 'POST',
      body: createParentUploadForm(),
    });

    assert.equal(response.status, 413);
    const payload = await response.json();
    assert.equal(payload.error, '题图文件太大，请缩小框选范围后重试');
    assert.equal(payload.retryable, false);
  } finally {
    globalThis.fetch = originalFetch;
    for (const fileName of uploadedFiles) {
      fs.rmSync(path.join(UPLOADS_DIR, fileName), { force: true });
    }
  }
});

test('parent upload bridge maps website enqueue failures as retryable', async (t) => {
  const originalFetch = globalThis.fetch;
  const uploadedFiles: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-questions') {
      const body = JSON.parse(String(init?.body || '{}'));
      trackUploadedFileFromImageUrl(uploadedFiles, body.image_url);
      return createJsonResponse({
        error: '上传任务暂时无法入队，请稍后重试',
        retryable: true,
        task: {
          id: 9104,
          status: 'failed',
          error_message: 'queue unavailable',
        },
      }, 502);
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions`, {
      method: 'POST',
      body: createParentUploadForm(),
    });

    assert.equal(response.status, 502);
    const payload = await response.json();
    assert.equal(payload.error, '上传任务暂时无法入队，请稍后重试');
    assert.equal(payload.retryable, true);
    assert.equal(payload.task.id, 9104);
  } finally {
    globalThis.fetch = originalFetch;
    for (const fileName of uploadedFiles) {
      fs.rmSync(path.join(UPLOADS_DIR, fileName), { force: true });
    }
  }
});

test('parent upload bridge maps website timeout as retryable gateway timeout', async (t) => {
  const originalFetch = globalThis.fetch;
  const uploadedFiles: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-questions') {
      const body = JSON.parse(String(init?.body || '{}'));
      trackUploadedFileFromImageUrl(uploadedFiles, body.image_url);
      throw new DOMException('The operation was aborted.', 'AbortError');
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions`, {
      method: 'POST',
      body: createParentUploadForm(),
    });

    assert.equal(response.status, 504);
    const payload = await response.json();
    assert.equal(payload.error, '网站上传接口超时，请稍后重试');
    assert.equal(payload.retryable, true);
  } finally {
    globalThis.fetch = originalFetch;
    for (const fileName of uploadedFiles) {
      fs.rmSync(path.join(UPLOADS_DIR, fileName), { force: true });
    }
  }
});

test('parent upload bridge maps malformed website acceptance responses as retryable upstream failures', async (t) => {
  const originalFetch = globalThis.fetch;
  const uploadedFiles: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-questions') {
      const body = JSON.parse(String(init?.body || '{}'));
      trackUploadedFileFromImageUrl(uploadedFiles, body.image_url);
      return new Response('not json', {
        status: 202,
        headers: {
          'content-type': 'text/plain',
        },
      });
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions`, {
      method: 'POST',
      body: createParentUploadForm(),
    });

    assert.equal(response.status, 502);
    const payload = await response.json();
    assert.equal(payload.error, '网站上传接口返回异常，请稍后重试');
    assert.equal(payload.retryable, true);
  } finally {
    globalThis.fetch = originalFetch;
    for (const fileName of uploadedFiles) {
      fs.rmSync(path.join(UPLOADS_DIR, fileName), { force: true });
    }
  }
});

test('parent upload task bridge forwards task status requests to the website', async (t) => {
  const originalFetch = globalThis.fetch;
  const websiteCalls: Array<{ url: string }> = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-question-upload-tasks/9001?open_id=openid-parent-1') {
      websiteCalls.push({ url });
      return createJsonResponse({
        task: {
          id: 9001,
          status: 'ready',
          record_id: 'wechat-record-1',
        },
      });
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-question-upload-tasks/9001?openId=openid-parent-1`);

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.task.status, 'ready');
    assert.equal(payload.task.record_id, 'wechat-record-1');
    assert.equal(websiteCalls.length, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent reason transcription bridge returns a non-empty legacy fallback without calling website transcription', async (t) => {
  const originalFetch = globalThis.fetch;
  const websiteCalls: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/reason-transcriptions') {
      websiteCalls.push(String(init?.body || ''));
      return new Promise<Response>(() => {});
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120);

    try {
      const response = await fetch(`${baseUrl}/wechat/parent/reason-transcriptions`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
        },
        body: JSON.stringify({
          audioUrl: 'https://example.com/files/voice-reason.mp3',
        }),
        signal: controller.signal,
      });

      assert.equal(response.status, 200);
      const payload = await response.json();
      assert.match(payload.transcript_text, /语音说明已上传/);
      assert.deepEqual(websiteCalls, []);
    } finally {
      clearTimeout(timeout);
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent reason classification bridge returns immediately without calling website classification', async (t) => {
  const originalFetch = globalThis.fetch;
  const websiteCalls: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/reason-classifications') {
      websiteCalls.push(String(init?.body || ''));
      return new Promise<Response>(() => {});
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120);

    try {
      const response = await fetch(`${baseUrl}/wechat/parent/reason-classifications`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
        },
        body: JSON.stringify({
          childReasonText: '我把单位换算漏掉了',
        }),
        signal: controller.signal,
      });

      assert.equal(response.status, 200);
      const payload = await response.json();
      assert.equal(payload.display_text, '我把单位换算漏掉了');
      assert.equal(payload.primary_error_type, '');
      assert.equal(payload.secondary_error_summary, '');
      assert.deepEqual(websiteCalls, []);
    } finally {
      clearTimeout(timeout);
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('generic upload route stores the file and returns a public file url', async (t) => {
  const server = await startTestServer(t);
  const address = server.address();
  assert.ok(address && typeof address === 'object');
  const baseUrl = `http://127.0.0.1:${address.port}`;
  const formData = new FormData();
  formData.set('file', new Blob(['mock-audio']), 'voice-reason.mp3');

  const response = await fetch(`${baseUrl}/upload`, {
    method: 'POST',
    body: formData,
  });

  assert.equal(response.status, 201);
  const payload = await response.json();
  assert.match(String(payload.url || ''), /^http:\/\/127\.0\.0\.1:\d+\/files\/.+/);
  assert.ok(String(payload.name || '').endsWith('.mp3'));

  const fileName = String(payload.name || '');
  const uploadedPath = fileName ? path.join(UPLOADS_DIR, fileName) : '';
  assert.ok(uploadedPath);
  assert.equal(fs.existsSync(uploadedPath), true);

  t.after(() => {
    if (uploadedPath) {
      fs.rmSync(uploadedPath, { force: true });
    }
  });
});

test('files route serves legacy upload files after bridge directory moves', async (t) => {
  fs.mkdirSync(LEGACY_UPLOADS_DIR, { recursive: true });
  const legacyFileName = `legacy-${Date.now()}.txt`;
  const legacyPath = path.join(LEGACY_UPLOADS_DIR, legacyFileName);
  fs.writeFileSync(legacyPath, 'legacy-image-bytes');
  t.after(() => {
    fs.rmSync(legacyPath, { force: true });
    fs.rmSync(LEGACY_UPLOADS_DIR, { recursive: true, force: true });
  });

  const server = await startTestServer(t);
  const address = server.address();
  assert.ok(address && typeof address === 'object');
  const baseUrl = `http://127.0.0.1:${address.port}`;

  const response = await fetch(`${baseUrl}/files/${legacyFileName}`);

  assert.equal(response.status, 200);
  assert.equal(await response.text(), 'legacy-image-bytes');
});

test('parent bridge no longer exposes the AI box route', async (t) => {
  const server = await startTestServer(t);
  const address = server.address();
  assert.ok(address && typeof address === 'object');
  const baseUrl = `http://127.0.0.1:${address.port}`;
  const formData = new FormData();
  formData.set('file', new Blob(['mock-image']), 'wrong-question-box.txt');

  const response = await fetch(`${baseUrl}/wechat/parent/wrong-question-boxes`, {
    method: 'POST',
    body: formData,
  });

  assert.equal(response.status, 404);
});

test('legacy chat and roster routes are no longer exposed by the parent-only bridge', async (t) => {
  const server = await startTestServer(t);
  const address = server.address();
  assert.ok(address && typeof address === 'object');
  const baseUrl = `http://127.0.0.1:${address.port}`;

  const roomsResponse = await fetch(`${baseUrl}/rooms`);
  const configResponse = await fetch(`${baseUrl}/wechat/config`);

  assert.equal(roomsResponse.status, 404);
  assert.equal(configResponse.status, 404);
});
