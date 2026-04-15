# Parent Voice Reason Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add child voice reason input to the parent upload flow, replace the old six-label taxonomy with four top-level labels across website and mini program, and store the final teacher-facing reason text plus AI note through the existing website fields.

**Architecture:** Keep the current three-hop structure: mini program UI -> Node bridge -> website API. The website becomes the source of truth for taxonomy, validation, and persisted fields; the bridge stays thin and proxies audio/text requests; the mini program collects text or audio per box, shows the teacher-facing summary before submit, and submits only finalized values. Reuse the existing website columns `child_raw_reason_text`, `primary_error_type`, `secondary_error_summary`, and `child_reason_input_mode`, but redefine their business semantics.

**Tech Stack:** Python Flask website backend, React + TypeScript website frontend, Express + TypeScript bridge backend, WeChat Mini Program page JS/WXML/WXSS, `unittest`, `tsx --test`, and `node:test`.

---

## File Structure

**Create**

- `docs/superpowers/plans/2026-04-10-parent-voice-reason-plan.md`

**Modify**

- `/Users/ark.mini/Desktop/Xingrun-Website/ai_processor.py`
- `/Users/ark.mini/Desktop/Xingrun-Website/app.py`
- `/Users/ark.mini/Desktop/Xingrun-Website/tests/test_wechat_parent_upload_api.py`
- `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/smartWrongQuestions.ts`
- `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/SmartWrongQuestionsPage.tsx`
- `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/smart-wrong-questions.test.ts`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/website-client.ts`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/index.ts`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/parent-wechat-bridge.test.ts`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/utils/parentApi.js`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/utils/parentApi.test.js`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/model.js`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/model.test.js`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/index.js`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/index.wxml`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/index.wxss`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/parent-only-scope.test.js`
- `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/handoff.md`

**Responsibility Map**

- `ai_processor.py`: own the four-label taxonomy, audio transcription helper, and reason-cleanup/classification prompt.
- `app.py`: expose website service endpoints for transcription and classification, and change final submit to persist caller-provided finalized reason data.
- `tests/test_wechat_parent_upload_api.py`: lock the new website API contract before implementation.
- `frontend/src/smartWrongQuestions.ts`: normalize website reason fields for teacher UI.
- `frontend/src/SmartWrongQuestionsPage.tsx`: replace old labels and options with the new teacher-facing copy and four-class taxonomy.
- `backend/src/website-client.ts`: bridge-to-website proxy helpers for transcription, classification, and final submit fields.
- `backend/src/index.ts`: bridge routes for `/wechat/parent/reason-transcriptions`, `/wechat/parent/reason-classifications`, and updated final submit forwarding.
- `miniprogram/utils/parentApi.js`: client calls for text classification, audio transcription, and finalized submit payload.
- `miniprogram/pages/parent-upload/model.js`: pure state helpers for per-box reason draft, finalized text, top-level label, note, and submit blockers.
- `miniprogram/pages/parent-upload/index.*`: UI and orchestration for text/voice reason entry and confirmation.

## Task 1: Replace website taxonomy and split website reason APIs

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/tests/test_wechat_parent_upload_api.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/ai_processor.py`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/app.py`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/tests/test_wechat_parent_upload_api.py`

- [ ] **Step 1: Write failing website API tests for transcription, classification, and finalized submit**

Add these tests to `/Users/ark.mini/Desktop/Xingrun-Website/tests/test_wechat_parent_upload_api.py` inside `WeChatParentUploadApiTestCase`:

```python
    @patch("app.ai_processor.transcribe_child_reason_audio", return_value={"transcript_text": "我把单位换算漏掉了"})
    def test_wechat_service_can_transcribe_child_reason_audio(self, mock_transcribe):
        response = self.client.post(
            "/api/wechat/reason-transcriptions",
            headers=self.service_headers(),
            json={"audio_url": "https://files.example.com/reason.m4a"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["transcript_text"], "我把单位换算漏掉了")
        mock_transcribe.assert_called_once_with("https://files.example.com/reason.m4a")

    @patch(
        "app.ai_processor.classify_wrong_question_reason",
        return_value={
            "display_text": "单位换算这一步漏掉了，后续计算也因此出错",
            "primary_error_type": "细节问题",
            "secondary_error_summary": "主要表现为单位换算遗漏，并带来后续计算偏差。",
        },
    )
    def test_wechat_service_can_classify_child_reason_text(self, mock_classify):
        response = self.client.post(
            "/api/wechat/reason-classifications",
            headers=self.service_headers(),
            json={"child_reason_text": "我把单位换算漏掉了，然后后面也有点写快了"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["display_text"], "单位换算这一步漏掉了，后续计算也因此出错")
        self.assertEqual(payload["primary_error_type"], "细节问题")
        self.assertEqual(payload["secondary_error_summary"], "主要表现为单位换算遗漏，并带来后续计算偏差。")
        mock_classify.assert_called_once_with("我把单位换算漏掉了，然后后面也有点写快了")

    @patch("app.ai_processor.recognize_wrong_question_image", return_value=WeChatParentUploadApiTestCase.recognized_payload())
    @patch("app._rebuild_student_wrong_question_library", return_value="/tmp/student-1.pdf")
    @patch("app.ai_processor.classify_wrong_question_reason")
    def test_wechat_upload_persists_finalized_reason_fields_without_reclassifying(self, mock_classify, _mock_rebuild, _mock_recognize):
        self.client.post(
            "/api/wechat/login",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "nickname_snapshot": "Alice 妈妈"},
        )
        bind = self.client.post(
            "/api/wechat/bind-student",
            headers=self.service_headers(),
            json={"open_id": "openid-1", "class_id": self.class_id, "student_id": self.student["id"]},
        )
        binding = bind.get_json()["binding"]

        response = self.client.post(
            "/api/wechat/wrong-questions",
            headers=self.service_headers(),
            json={
                "open_id": "openid-1",
                "binding_id": binding["id"],
                "image_url": "https://files.example.com/record.png",
                "child_raw_reason_text": "单位换算这一步漏掉了，后续计算也因此出错",
                "child_reason_input_mode": "voice",
                "primary_error_type": "细节问题",
                "secondary_error_summary": "主要表现为单位换算遗漏，并带来后续计算偏差。",
            },
        )

        self.assertEqual(response.status_code, 201)
        record = response.get_json()["record"]
        self.assertEqual(record["child_raw_reason_text"], "单位换算这一步漏掉了，后续计算也因此出错")
        self.assertEqual(record["child_reason_input_mode"], "voice")
        self.assertEqual(record["primary_error_type"], "细节问题")
        self.assertEqual(record["secondary_error_summary"], "主要表现为单位换算遗漏，并带来后续计算偏差。")
        mock_classify.assert_not_called()
```

- [ ] **Step 2: Run the website API tests and verify they fail**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
python3 -m unittest \
  tests.test_wechat_parent_upload_api.WeChatParentUploadApiTestCase.test_wechat_service_can_transcribe_child_reason_audio \
  tests.test_wechat_parent_upload_api.WeChatParentUploadApiTestCase.test_wechat_service_can_classify_child_reason_text \
  tests.test_wechat_parent_upload_api.WeChatParentUploadApiTestCase.test_wechat_upload_persists_finalized_reason_fields_without_reclassifying
```

Expected: FAIL because the new endpoints do not exist and `/api/wechat/wrong-questions` still calls the old six-label classifier internally.

- [ ] **Step 3: Implement the four-label taxonomy and website endpoints**

In `/Users/ark.mini/Desktop/Xingrun-Website/ai_processor.py`, replace the old options with this shape:

```python
WRONG_QUESTION_ERROR_TYPE_OPTIONS = [
    "知识点问题",
    "细节问题",
    "方法问题",
    "审题问题",
]

WRONG_QUESTION_REASON_CLASSIFICATION_PROMPT = """你是错因整理助手。
你会收到孩子对错因的自然口述或手打文本。

你必须完成三件事：
1. 把内容整理成老师可直接阅读的一段自然中文
2. 只从以下四个顶层分类中选择一个最接近的标签：知识点问题、细节问题、方法问题、审题问题
3. 生成一段补充备注，用于解释更细的表现，例如单位、符号、书写、漏条件、辅助线、运算顺序

只返回 JSON，不要输出额外解释。
返回字段必须包含：
- display_text: string
- primary_error_type: string，且必须是以上四个固定值之一
- secondary_error_summary: string

规则：
- display_text 使用老师能直接阅读的自然中文
- 删除口头禅、重复语和无效停顿
- 不凭空添加孩子没有表达过的信息
- secondary_error_summary 不要简单复述 primary_error_type
"""

def classify_wrong_question_reason(child_reason_text: str) -> dict:
    normalized_reason_text = str(child_reason_text or "").strip()
    if not normalized_reason_text:
        raise ValueError("child_reason_text is required")

    client = _get_client()
    response = client.chat.completions.create(
        model=_get_structured_generation_model(),
        messages=[
            {"role": "system", "content": WRONG_QUESTION_REASON_CLASSIFICATION_PROMPT},
            {"role": "user", "content": json.dumps({"child_reason_text": normalized_reason_text}, ensure_ascii=False)},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    display_text = str(payload.get("display_text") or "").strip()
    primary_error_type = str(payload.get("primary_error_type") or "").strip()
    secondary_error_summary = str(payload.get("secondary_error_summary") or "").strip()

    if primary_error_type not in WRONG_QUESTION_ERROR_TYPE_OPTIONS:
        raise ValueError("wrong question reason classification failed")
    if not display_text or not secondary_error_summary:
        raise ValueError("wrong question reason classification failed")

    return {
        "display_text": display_text,
        "primary_error_type": primary_error_type,
        "secondary_error_summary": secondary_error_summary,
    }
```

Add audio transcription support to the same file:

```python
def transcribe_child_reason_audio(audio_url: str) -> dict:
    normalized_audio_url = str(audio_url or "").strip()
    if not normalized_audio_url:
        raise ValueError("audio_url is required")

    with urllib.request.urlopen(normalized_audio_url, timeout=20) as response:
        audio_bytes = response.read()

    suffix = Path(urllib.parse.urlparse(normalized_audio_url).path).suffix or ".m4a"
    with tempfile.NamedTemporaryFile(suffix=suffix) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_audio.flush()
        with open(temp_audio.name, "rb") as audio_file:
            transcript = _get_client().audio.transcriptions.create(
                model=_get_transcription_model(),
                file=audio_file,
                prompt="这是小学生或初中生描述数学错因的中文语音，请尽量保留数学术语、单位、符号、辅助线、审题、方法等词。",
            )

    transcript_text = str(getattr(transcript, "text", "") or "").strip()
    if not transcript_text:
        raise ValueError("audio transcription failed")
    return {"transcript_text": transcript_text}
```

In `/Users/ark.mini/Desktop/Xingrun-Website/app.py`, add these routes and change final submit validation:

```python
@app.route("/api/wechat/reason-transcriptions", methods=["POST"])
def api_wechat_reason_transcriptions_create():
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    audio_url = (data.get("audio_url") or "").strip()
    if not audio_url:
        return jsonify({"error": "audio_url is required"}), 400

    try:
        return jsonify(ai_processor.transcribe_child_reason_audio(audio_url))
    except ValueError as exc:
        return jsonify({"error": str(exc), "retryable": True}), 422
    except Exception as exc:
        return jsonify({"error": str(exc), "retryable": True}), 502


@app.route("/api/wechat/reason-classifications", methods=["POST"])
def api_wechat_reason_classifications_create():
    _, error = _require_wechat_service()
    if error:
        return error
    data, error = _get_json_object_payload()
    if error:
        return error

    child_reason_text = (data.get("child_reason_text") or "").strip()
    if not child_reason_text:
        return jsonify({"error": "child_reason_text is required"}), 400

    try:
        return jsonify(ai_processor.classify_wrong_question_reason(child_reason_text))
    except ValueError as exc:
        return jsonify({"error": str(exc), "retryable": True}), 422
    except Exception as exc:
        return jsonify({"error": str(exc), "retryable": True}), 502
```

Inside `api_wechat_wrong_questions_create`, replace the old classification block with direct validation:

```python
    primary_error_type = (data.get("primary_error_type") or "").strip()
    secondary_error_summary = (data.get("secondary_error_summary") or "").strip()
    if primary_error_type not in ai_processor.WRONG_QUESTION_ERROR_TYPE_OPTIONS:
        return jsonify({"error": "primary_error_type is invalid"}), 400
    if not secondary_error_summary:
        return jsonify({"error": "secondary_error_summary is required"}), 400
```

and persist those values directly when calling `create_wechat_wrong_question_submission(...)`.

- [ ] **Step 4: Run the focused website API tests and verify they pass**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
python3 -m unittest \
  tests.test_wechat_parent_upload_api.WeChatParentUploadApiTestCase.test_wechat_service_can_transcribe_child_reason_audio \
  tests.test_wechat_parent_upload_api.WeChatParentUploadApiTestCase.test_wechat_service_can_classify_child_reason_text \
  tests.test_wechat_parent_upload_api.WeChatParentUploadApiTestCase.test_wechat_upload_persists_finalized_reason_fields_without_reclassifying
```

Expected: PASS with 3 passing tests.

- [ ] **Step 5: Commit the website API contract slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git add ai_processor.py app.py tests/test_wechat_parent_upload_api.py
git commit -m "feat: add parent voice reason website apis"
```

## Task 2: Replace teacher UI labels and four-class taxonomy on website

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/smartWrongQuestions.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/SmartWrongQuestionsPage.tsx`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/smart-wrong-questions.test.ts`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Write the failing website frontend tests for the new labels and taxonomy**

Add or update assertions in `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/smart-wrong-questions.test.ts`:

```ts
test('normalizeWrongQuestionRecord keeps website reason fields for teacher display', () => {
  const normalized = normalizeWrongQuestionRecord({
    source: 'wechat_mp',
    child_raw_reason_text: '单位换算这一步漏掉了，后续计算也因此出错',
    child_reason_input_mode: 'voice',
    primary_error_type: '细节问题',
    secondary_error_summary: '主要表现为单位换算遗漏，并带来后续计算偏差。',
    analysis: {},
  });

  assert.equal(normalized.childReasonText, '单位换算这一步漏掉了，后续计算也因此出错');
  assert.equal(normalized.primaryErrorType, '细节问题');
  assert.equal(normalized.causeNote, '主要表现为单位换算遗漏，并带来后续计算偏差。');
});

test('smart wrong question page shows the new teacher-facing reason labels', async () => {
  const pageText = await renderSmartWrongQuestionsPageWithWechatRecord({
    child_raw_reason_text: '单位换算这一步漏掉了，后续计算也因此出错',
    primary_error_type: '细节问题',
    secondary_error_summary: '主要表现为单位换算遗漏，并带来后续计算偏差。',
  });

  assert.match(pageText, /孩子错因描述/);
  assert.match(pageText, /错因分类/);
  assert.match(pageText, /补充备注/);
  assert.doesNotMatch(pageText, /孩子自述错因/);
  assert.doesNotMatch(pageText, /AI 归类错因/);
});
```

- [ ] **Step 2: Run the website frontend tests and verify they fail**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npm test -- --test-name-pattern="normalizeWrongQuestionRecord|teacher-facing reason labels"
```

Expected: FAIL because the option list and UI labels still reference the old six-label vocabulary.

- [ ] **Step 3: Implement the website frontend taxonomy and labels**

Update `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/SmartWrongQuestionsPage.tsx`:

```ts
const WRONG_QUESTION_ERROR_TYPE_OPTIONS = [
  '知识点问题',
  '细节问题',
  '方法问题',
  '审题问题',
];
```

Replace the teacher-facing labels in the detail panel:

```tsx
<p className="text-xs uppercase tracking-[0.2em] text-slate-400">孩子错因描述</p>
<p className="mt-2 whitespace-pre-wrap text-sm text-slate-600 dark:text-slate-300">{selectedRecord.childReasonText || '暂未生成孩子错因描述。'}</p>

<p className="text-xs uppercase tracking-[0.2em] text-slate-400">错因分类</p>
<p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">{selectedRecord.primaryErrorType || '待归类'}</p>

<p className="text-xs uppercase tracking-[0.2em] text-slate-400">补充备注</p>
<p className="mt-2 whitespace-pre-wrap text-sm text-slate-600 dark:text-slate-300">{selectedRecord.causeNote || '暂未生成补充备注。'}</p>
```

Keep `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/smartWrongQuestions.ts` field mappings unchanged, but add a short inline comment above the `childReasonText` mapping to document that website now stores the teacher-facing final text in `child_raw_reason_text`.

- [ ] **Step 4: Run the website frontend tests and verify they pass**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npm test -- --test-name-pattern="normalizeWrongQuestionRecord|teacher-facing reason labels"
```

Expected: PASS with the targeted frontend cases green.

- [ ] **Step 5: Commit the website frontend slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
git add frontend/src/smartWrongQuestions.ts frontend/src/SmartWrongQuestionsPage.tsx frontend/src/smart-wrong-questions.test.ts
git commit -m "feat: update teacher reason taxonomy display"
```

## Task 3: Add bridge proxies for transcription, classification, and finalized submit fields

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/parent-wechat-bridge.test.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/website-client.ts`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/index.ts`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/parent-wechat-bridge.test.ts`

- [ ] **Step 1: Write the failing bridge tests for transcription/classification proxies**

Add these tests to `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/parent-wechat-bridge.test.ts`:

```ts
test('parent reason transcription bridge stores the audio file and forwards audio_url to website', async (t) => {
  const originalFetch = globalThis.fetch;
  let forwardedBody: Record<string, unknown> | null = null;

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/reason-transcriptions') {
      forwardedBody = JSON.parse(String(init?.body || '{}'));
      return createJsonResponse({ transcript_text: '我把单位换算漏掉了' });
    }
    return originalFetch(input as RequestInfo | URL, init);
  }) as typeof fetch;

  try {
    const server = await startTestServer(t);
    const address = server.address();
    assert.ok(address && typeof address === 'object');
    const baseUrl = `http://127.0.0.1:${address.port}`;
    const formData = new FormData();
    formData.set('file', new Blob(['mock-audio']), 'reason.m4a');

    const response = await fetch(`${baseUrl}/wechat/parent/reason-transcriptions`, { method: 'POST', body: formData });
    assert.equal(response.status, 200);
    assert.equal((await response.json()).transcriptText, '我把单位换算漏掉了');
    assert.match(String(forwardedBody?.audio_url || ''), /^http:\/\/127\.0\.0\.1:\d+\/files\//);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('parent reason classification bridge forwards child reason text and returns finalized reason fields', async (t) => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url === 'https://website.example/api/wechat/reason-classifications') {
      const body = JSON.parse(String(init?.body || '{}'));
      assert.equal(body.child_reason_text, '我把单位换算漏掉了');
      return createJsonResponse({
        display_text: '单位换算这一步漏掉了，后续计算也因此出错',
        primary_error_type: '细节问题',
        secondary_error_summary: '主要表现为单位换算遗漏，并带来后续计算偏差。',
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
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ childReasonText: '我把单位换算漏掉了' }),
    });

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      displayText: '单位换算这一步漏掉了，后续计算也因此出错',
      primaryErrorType: '细节问题',
      secondaryErrorSummary: '主要表现为单位换算遗漏，并带来后续计算偏差。',
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
```

- [ ] **Step 2: Run the bridge tests and verify they fail**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend
node --import tsx --test src/parent-wechat-bridge.test.ts
```

Expected: FAIL because the new routes and website proxy helpers do not exist yet.

- [ ] **Step 3: Implement the bridge proxy helpers and routes**

In `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/website-client.ts`, add:

```ts
export async function transcribeParentReasonOnWebsite(input: { audioUrl: string }) {
  return requestWebsite<{ transcript_text: string }>('/api/wechat/reason-transcriptions', {
    method: 'POST',
    body: { audio_url: input.audioUrl },
  });
}

export async function classifyParentReasonOnWebsite(input: { childReasonText: string }) {
  return requestWebsite<{ display_text: string; primary_error_type: string; secondary_error_summary: string }>('/api/wechat/reason-classifications', {
    method: 'POST',
    body: { child_reason_text: input.childReasonText },
  });
}
```

Update `submitWechatWrongQuestionToWebsite(...)` so it forwards finalized fields:

```ts
export async function submitWechatWrongQuestionToWebsite(input: {
  openId: string;
  bindingId: number;
  imageUrl: string;
  childRawReasonText: string;
  childReasonInputMode?: string;
  primaryErrorType: string;
  secondaryErrorSummary: string;
}) {
  return requestWebsite<{ record: WebsiteWrongQuestionSubmission }>('/api/wechat/wrong-questions', {
    method: 'POST',
    body: {
      open_id: input.openId,
      binding_id: input.bindingId,
      image_url: input.imageUrl,
      child_raw_reason_text: input.childRawReasonText,
      child_reason_input_mode: input.childReasonInputMode || 'text',
      primary_error_type: input.primaryErrorType,
      secondary_error_summary: input.secondaryErrorSummary,
    },
  });
}
```

In `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/index.ts`, add routes:

```ts
  app.post('/wechat/parent/reason-transcriptions', upload.single('file'), async (req, res) => {
    const uploadedAudioUrl = req.file ? `${getBaseUrl(req.get('host'))}/files/${req.file.filename}` : '';
    if (!uploadedAudioUrl) {
      res.status(400).json({ error: 'file required' });
      return;
    }

    try {
      const payload = await transcribeParentReasonOnWebsite({ audioUrl: uploadedAudioUrl });
      res.json({ transcriptText: payload.transcript_text });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  });

  app.post('/wechat/parent/reason-classifications', async (req, res) => {
    const childReasonText = String(req.body?.childReasonText ?? req.body?.child_reason_text ?? '').trim();
    if (!childReasonText) {
      res.status(400).json({ error: 'childReasonText required' });
      return;
    }

    try {
      const payload = await classifyParentReasonOnWebsite({ childReasonText });
      res.json({
        displayText: payload.display_text,
        primaryErrorType: payload.primary_error_type,
        secondaryErrorSummary: payload.secondary_error_summary,
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  });
```

Update the existing submit route so it also reads `primaryErrorType` / `secondaryErrorSummary` from form data and forwards them to `submitWechatWrongQuestionToWebsite(...)`.

- [ ] **Step 4: Run the bridge tests and verify they pass**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend
node --import tsx --test src/parent-wechat-bridge.test.ts
```

Expected: PASS with the new transcription/classification bridge cases green.

- [ ] **Step 5: Commit the bridge slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
git add backend/src/website-client.ts backend/src/index.ts backend/src/parent-wechat-bridge.test.ts
git commit -m "feat: add parent voice reason bridge routes"
```

## Task 4: Extend mini program helpers and pure model for finalized reason data

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/utils/parentApi.test.js`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/utils/parentApi.js`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/model.test.js`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/model.js`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/utils/parentApi.test.js`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/model.test.js`

- [ ] **Step 1: Write failing helper and model tests for finalized reason fields**

Add these tests to `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/utils/parentApi.test.js`:

```js
test('transcribeParentReason returns transcriptText from the bridge', async () => {
  const wxApi = {
    uploadFile({ url, success }) {
      assert.match(url, /\/wechat\/parent\/reason-transcriptions$/);
      success({ statusCode: 200, data: JSON.stringify({ transcriptText: '我把单位换算漏掉了' }) });
    },
  };

  const payload = await transcribeParentReason(wxApi, 'https://example.com', { filePath: '/tmp/reason.m4a' });
  assert.equal(payload.transcriptText, '我把单位换算漏掉了');
});

test('classifyParentReason returns teacher-facing reason fields from the bridge', async () => {
  const wxApi = {
    request({ url, method, data, success }) {
      assert.match(url, /\/wechat\/parent\/reason-classifications$/);
      assert.equal(method, 'POST');
      assert.equal(data.childReasonText, '我把单位换算漏掉了');
      success({
        statusCode: 200,
        data: {
          displayText: '单位换算这一步漏掉了，后续计算也因此出错',
          primaryErrorType: '细节问题',
          secondaryErrorSummary: '主要表现为单位换算遗漏，并带来后续计算偏差。',
        },
      });
    },
  };

  const payload = await classifyParentReason(wxApi, 'https://example.com', { childReasonText: '我把单位换算漏掉了' });
  assert.equal(payload.primaryErrorType, '细节问题');
});
```

Add these tests to `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/model.test.js`:

```js
test('addManualBoxToImage creates finalized reason placeholders for each box', () => {
  const next = addManualBoxToImage({ id: 'img_1', localPath: 'a.jpg', aiStatus: 'idle', boxes: [], activeBoxId: '' });
  assert.equal(next.boxes[0].childReasonText, '');
  assert.equal(next.boxes[0].primaryErrorType, '');
  assert.equal(next.boxes[0].secondaryErrorSummary, '');
  assert.equal(next.boxes[0].childReasonInputMode, 'text');
});

test('getSubmitBlockers requires finalized reason text, top-level type, and note', () => {
  const blockers = getSubmitBlockers([
    {
      id: 'img_1',
      aiStatus: 'done',
      boxes: [
        { id: 'box_1', childReasonText: '单位换算这一步漏掉了', primaryErrorType: '细节问题', secondaryErrorSummary: '主要表现为单位换算遗漏。' },
        { id: 'box_2', childReasonText: '我算错了', primaryErrorType: '', secondaryErrorSummary: '' },
      ],
    },
  ]);

  assert.deepEqual(blockers, {
    emptyImageIds: [],
    runningImageIds: [],
    missingReasonBoxIds: ['box_2'],
  });
});
```

- [ ] **Step 2: Run the helper and model tests and verify they fail**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
node --test miniprogram/utils/parentApi.test.js
node --test miniprogram/pages/parent-upload/model.test.js
```

Expected: FAIL because the new API helpers are missing and boxes do not yet track finalized reason fields.

- [ ] **Step 3: Implement the mini program API helpers and pure state changes**

In `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/utils/parentApi.js`, add:

```js
async function transcribeParentReason(wxApi, serverUrl, params) {
  return uploadFile(wxApi, {
    url: `${serverUrl}/wechat/parent/reason-transcriptions`,
    filePath: params.filePath,
    name: 'file',
    formData: {},
  });
}

async function classifyParentReason(wxApi, serverUrl, params) {
  return requestJson(wxApi, {
    url: `${serverUrl}/wechat/parent/reason-classifications`,
    method: 'POST',
    data: { childReasonText: params.childReasonText },
  });
}
```

Update `submitParentWrongQuestion(...)` to include finalized reason fields:

```js
      childRawReasonText: params.childRawReasonText || '',
      childReasonInputMode: params.childReasonInputMode || 'text',
      primaryErrorType: params.primaryErrorType || '',
      secondaryErrorSummary: params.secondaryErrorSummary || '',
```

and export the new helpers.

In `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/model.js`, change the default box shape and upload jobs:

```js
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
    primaryErrorType: '',
    secondaryErrorSummary: '',
    reasonStatus: 'idle',
  };
}
```

and in `buildUploadJobs(...)`:

```js
      childRawReasonText: String(box.childReasonText || '').trim(),
      childReasonInputMode: String(box.childReasonInputMode || 'text').trim() || 'text',
      primaryErrorType: String(box.primaryErrorType || '').trim(),
      secondaryErrorSummary: String(box.secondaryErrorSummary || '').trim(),
```

Update `getSubmitBlockers(...)` so any box missing any of the three finalized reason values remains blocked.

- [ ] **Step 4: Run the helper and model tests and verify they pass**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
node --test miniprogram/utils/parentApi.test.js
node --test miniprogram/pages/parent-upload/model.test.js
```

Expected: PASS with the new helper/model cases green.

- [ ] **Step 5: Commit the mini program helper slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
git add miniprogram/utils/parentApi.js miniprogram/utils/parentApi.test.js miniprogram/pages/parent-upload/model.js miniprogram/pages/parent-upload/model.test.js
git commit -m "feat: add finalized parent reason helpers"
```

## Task 5: Add mini program voice/text reason UI and page orchestration

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/index.js`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/index.wxml`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/index.wxss`
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/parent-only-scope.test.js`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/parent-only-scope.test.js`

- [ ] **Step 1: Write the failing page-scope regression test for voice reason UI**

Add assertions to `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/parent-only-scope.test.js`:

```js
test('parent upload page exposes text and voice reason entry plus teacher-facing labels', () => {
  const wxml = fs.readFileSync(path.join(__dirname, 'pages/parent-upload/index.wxml'), 'utf8');
  assert.match(wxml, /孩子错因描述/);
  assert.match(wxml, /错因分类/);
  assert.match(wxml, /补充备注/);
  assert.match(wxml, /语音输入/);
  assert.match(wxml, /整理错因/);
});
```

- [ ] **Step 2: Run the mini program scope test and verify it fails**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
node miniprogram/parent-only-scope.test.js
```

Expected: FAIL because the page does not yet expose the new reason UI or labels.

- [ ] **Step 3: Implement the page orchestration and UI**

In `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/index.js`, import the new helpers and add per-box handlers:

```js
const {
  detectParentWrongQuestionBoxes,
  ensureParentSession,
  fetchParentBindings,
  submitParentWrongQuestion,
  transcribeParentReason,
  classifyParentReason,
} = require('../../utils/parentApi');
```

Add a reusable finalization method:

```js
  async finalizeBoxReason(boxId, draftText, inputMode) {
    const trimmed = String(draftText || '').trim();
    if (!trimmed) {
      this.setData({ errorMessage: '请先输入或说出孩子错因，再整理。' });
      return;
    }

    const payload = await classifyParentReason(wx, app.globalData.serverUrl, { childReasonText: trimmed });
    this.patchActiveBox(boxId, {
      childReasonText: payload.displayText,
      childReasonInputMode: inputMode,
      primaryErrorType: payload.primaryErrorType,
      secondaryErrorSummary: payload.secondaryErrorSummary,
      reasonStatus: 'done',
    });
  }
```

Add a voice flow method:

```js
  async transcribeVoiceForBox(tempFilePath, boxId) {
    const payload = await transcribeParentReason(wx, app.globalData.serverUrl, { filePath: tempFilePath });
    await this.finalizeBoxReason(boxId, payload.transcriptText, 'voice');
  }
```

Update the submit loop so each upload job forwards:

```js
        childRawReasonText: job.childRawReasonText,
        childReasonInputMode: job.childReasonInputMode,
        primaryErrorType: job.primaryErrorType,
        secondaryErrorSummary: job.secondaryErrorSummary,
```

In `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/index.wxml`, add a per-box reason card under the crop stage:

```xml
<view class="reason-card" wx:if="{{activeBox}}">
  <view class="reason-mode-row">
    <button class="compact-btn {{activeBox.childReasonInputMode !== 'voice' ? 'active-mode-btn' : ''}}" bindtap="setActiveBoxTextMode">手动输入</button>
    <button class="compact-btn {{activeBox.childReasonInputMode === 'voice' ? 'active-mode-btn' : ''}}" bindtap="startVoiceReason">语音输入</button>
  </view>
  <textarea class="reason-textarea" value="{{activeBox.childReasonText}}" placeholder="让孩子说清这题为什么错" bindinput="onActiveBoxReasonInput" />
  <button class="primary-btn" bindtap="finalizeActiveBoxReason">整理错因</button>

  <view class="reason-result" wx:if="{{activeBox.primaryErrorType}}">
    <text class="reason-label">孩子错因描述</text>
    <text class="reason-value">{{activeBox.childReasonText}}</text>
    <text class="reason-label">错因分类</text>
    <text class="reason-value">{{activeBox.primaryErrorType}}</text>
    <text class="reason-label">补充备注</text>
    <text class="reason-value">{{activeBox.secondaryErrorSummary}}</text>
  </view>
</view>
```

In `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/index.wxss`, add minimal styles:

```css
.reason-card {
  margin-top: 24rpx;
  padding: 24rpx;
  border-radius: 24rpx;
  background: #ffffff;
}

.reason-mode-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.reason-textarea {
  width: 100%;
  min-height: 180rpx;
  padding: 20rpx;
  border-radius: 20rpx;
  background: #f8fafc;
}

.reason-label {
  margin-top: 16rpx;
  font-size: 22rpx;
  color: #64748b;
}

.reason-value {
  display: block;
  margin-top: 8rpx;
  font-size: 28rpx;
  color: #0f172a;
}
```

- [ ] **Step 4: Run the mini program regression tests and verify they pass**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
node miniprogram/parent-only-scope.test.js
node --test miniprogram/pages/parent-upload/model.test.js
node --test miniprogram/utils/parentApi.test.js
```

Expected: PASS with the voice/text reason assertions green.

- [ ] **Step 5: Commit the mini program page slice**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
git add miniprogram/pages/parent-upload/index.js miniprogram/pages/parent-upload/index.wxml miniprogram/pages/parent-upload/index.wxss miniprogram/parent-only-scope.test.js
git commit -m "feat: add parent voice reason ui"
```

## Task 6: Full verification and handoff updates

**Files:**
- Modify: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/handoff.md`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/parent-only-scope.test.js`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/pages/parent-upload/model.test.js`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/miniprogram/utils/parentApi.test.js`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/backend/src/parent-wechat-bridge.test.ts`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/tests/test_wechat_parent_upload_api.py`
- Test: `/Users/ark.mini/Desktop/Xingrun-Website/frontend/src/smart-wrong-questions.test.ts`

- [ ] **Step 1: Update handoff with the implementation outcome and proof commands**

Append a dated note to `/Users/ark.mini/Desktop/Xingrun-Website/miniprogram/handoff.md` that records:

```md
## 2026-04-10 Parent Voice Reason Implementation
- website taxonomy switched to `知识点问题 / 细节问题 / 方法问题 / 审题问题`
- bridge now proxies child reason transcription and classification
- mini program parent upload page now supports text and voice reason entry per box
- teacher UI labels now use `孩子错因描述 / 错因分类 / 补充备注`
- proof commands listed below all passed before handoff
```

- [ ] **Step 2: Run website backend verification**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website
python3 -m unittest tests.test_wechat_parent_upload_api
```

Expected: PASS with the website API suite green.

- [ ] **Step 3: Run website frontend verification**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/frontend
npm test -- src/smart-wrong-questions.test.ts
```

Expected: PASS with the smart wrong questions frontend suite green.

- [ ] **Step 4: Run bridge and mini program verification**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
node --test miniprogram/utils/parentApi.test.js
node --test miniprogram/pages/parent-upload/model.test.js
node miniprogram/parent-only-scope.test.js
cd backend && node --import tsx --test src/parent-wechat-bridge.test.ts
```

Expected: PASS with all mini program and bridge tests green.

- [ ] **Step 5: Commit the final verification note**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Website/miniprogram
git add handoff.md docs/superpowers/plans/2026-04-10-parent-voice-reason-plan.md
git commit -m "docs: add parent voice reason implementation plan"
```