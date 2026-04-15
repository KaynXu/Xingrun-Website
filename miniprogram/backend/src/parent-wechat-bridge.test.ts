import assert from 'node:assert/strict';
import { once } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UPLOADS_DIR = path.resolve(__dirname, '../../uploads');

async function loadAppModule() {
  process.env.WEBSITE_API_BASE_URL = 'https://website.example';
  process.env.WEBSITE_API_TOKEN = 'wechat-service-token';
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
      assert.equal(body.primary_error_type, '细节问题');
      assert.equal(body.secondary_error_summary, '单位换算遗漏');
      assert.match(body.image_url, /^http:\/\/127\.0\.0\.1:\d+\/files\/.+/);

      const fileName = String(body.image_url).split('/files/')[1];
      uploadedFiles.push(fileName);

      return createJsonResponse({
        record: {
          id: 'wechat-record-1',
          binding_id: 21,
          class_id: 8,
          student_id: 101,
          teacher_user_id: 5,
          source: 'wechat_mp',
          status: 'pending',
          image_url: body.image_url,
        },
      }, 201);
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
    formData.set('primaryErrorType', '细节问题');
    formData.set('secondaryErrorSummary', '单位换算遗漏');
    formData.set('file', new Blob(['mock-image']), 'wrong-question.txt');

    const response = await fetch(`${baseUrl}/wechat/parent/wrong-questions`, {
      method: 'POST',
      body: formData,
    });

    assert.equal(response.status, 201);
    const payload = await response.json();
    assert.equal(payload.record.id, 'wechat-record-1');
    assert.equal(payload.record.source, 'wechat_mp');

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

test('parent reason transcription bridge forwards the audio url to the website', async (t) => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/reason-transcriptions') {
      const body = JSON.parse(String(init?.body || '{}'));
      assert.equal(body.audio_url, 'https://example.com/files/voice-reason.mp3');
      return createJsonResponse({
        transcript_text: '我把加法看成减法了',
      });
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/reason-transcriptions`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        audioUrl: 'https://example.com/files/voice-reason.mp3',
      }),
    });

    assert.equal(response.status, 200);
    assert.equal((await response.json()).transcript_text, '我把加法看成减法了');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent reason classification bridge forwards the child reason text to the website', async (t) => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/reason-classifications') {
      const body = JSON.parse(String(init?.body || '{}'));
      assert.equal(body.child_reason_text, '我把单位换算漏掉了');
      return createJsonResponse({
        display_text: '我把单位换算漏掉了',
        primary_error_type: '细节问题',
        secondary_error_summary: '单位换算遗漏',
      });
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;

    const response = await fetch(`${baseUrl}/wechat/parent/reason-classifications`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        childReasonText: '我把单位换算漏掉了',
      }),
    });

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.primary_error_type, '细节问题');
    assert.equal(payload.secondary_error_summary, '单位换算遗漏');
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

test('parent AI box bridge stores the file and forwards its image url to the website detector', async (t) => {
  const originalFetch = globalThis.fetch;
  const uploadedFiles: string[] = [];

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/wrong-question-boxes') {
      const body = JSON.parse(String(init?.body || '{}'));
      assert.match(body.image_url, /^http:\/\/127\.0\.0\.1:\d+\/files\/.+/);

      const fileName = String(body.image_url).split('/files/')[1];
      uploadedFiles.push(fileName);

      return createJsonResponse({
        boxes: [
          { x: 0.1, y: 0.2, width: 0.4, height: 0.3 },
          { x: 0.55, y: 0.5, width: 0.3, height: 0.22 },
        ],
      });
    }

    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
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

    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.boxes.length, 2);
    assert.deepEqual(payload.boxes[0], { x: 0.1, y: 0.2, width: 0.4, height: 0.3 });

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
