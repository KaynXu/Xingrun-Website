import 'dotenv/config';
import express from 'express';
import fs from 'fs';
import path from 'path';
import { createServer } from 'http';
import { fileURLToPath } from 'url';

import { upload } from './upload.js';
import {
  bindParentStudentOnWebsite,
  getWrongQuestionLibraryForChildOnWebsite,
  getWrongQuestionUploadTaskOnWebsite,
  listParentBindingsOnWebsite,
  listPrimaryTopicCategorySuggestionsOnWebsite,
  listWrongQuestionsForChildOnWebsite,
  loginParentWechatAccount,
  previewParentClassBinding,
  submitWechatWrongQuestionToWebsite,
  updateWrongQuestionTopicCategoryOnWebsite,
  WebsiteRequestError,
} from './website-client.js';
import { exchangeCodeForOpenId } from './wechat.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT ?? 3001);
const BASE_URL = process.env.BASE_URL;
const UPLOADS_DIR = path.join(__dirname, '../../uploads');
const DEFAULT_LEGACY_UPLOADS_DIRS = [
  '/home/ubuntu/xingrun-backend-repo/uploads',
  '/home/ubuntu/xingrun-backend-repo/backend/uploads',
];

function getLegacyUploadDirs() {
  const configuredDirs = String(process.env.LEGACY_UPLOADS_DIRS || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
  const seen = new Set<string>();
  return [...configuredDirs, ...DEFAULT_LEGACY_UPLOADS_DIRS]
    .map((item) => path.resolve(item))
    .filter((item) => {
      if (item === path.resolve(UPLOADS_DIR) || seen.has(item)) {
        return false;
      }
      seen.add(item);
      return true;
    });
}

function getBaseUrl(host?: string | null) {
  if (BASE_URL) return BASE_URL;
  if (host) return `http://${host}`;
  return `http://localhost:${PORT}`;
}

function isWebsiteRequestError(error: unknown): error is WebsiteRequestError {
  return error instanceof WebsiteRequestError || Boolean(
    error
    && typeof error === 'object'
    && (error as { name?: unknown }).name === 'WebsiteRequestError'
    && typeof (error as { statusCode?: unknown }).statusCode === 'number'
    && typeof (error as { retryable?: unknown }).retryable === 'boolean',
  );
}

function sendWebsiteUploadProxyError(res: express.Response, error: unknown) {
  if (isWebsiteRequestError(error)) {
    const body = { ...error.payload };
    if (typeof body.error !== 'string' || !body.error.trim()) {
      body.error = error.message;
    }
    body.retryable = error.retryable;
    res.status(error.statusCode).json(body);
    return;
  }

  res.status(500).json({
    error: error instanceof Error ? error.message : String(error),
  });
}

async function resolveParentOpenId(payload: Record<string, unknown> | undefined) {
  const directOpenId = String(payload?.openId ?? payload?.open_id ?? '').trim();
  if (directOpenId) {
    return directOpenId;
  }

  const code = String(payload?.code ?? '').trim();
  if (!code) {
    throw new Error('code required');
  }

  const result = await exchangeCodeForOpenId(code);
  return result.openId;
}

export function createApp() {
  const app = express();

  app.use(express.json());
  app.use('/files', express.static(UPLOADS_DIR));
  for (const legacyUploadDir of getLegacyUploadDirs()) {
    app.use('/files', express.static(legacyUploadDir));
  }

  app.get('/healthz', (_req, res) => {
    res.json({
      ok: true,
      service: 'xingrun-parent-wechat-bridge',
      timestamp: Date.now(),
    });
  });

  app.post('/upload', upload.single('file'), async (req, res) => {
    if (!req.file) {
      res.status(400).json({ error: 'file required' });
      return;
    }

    res.status(201).json({
      name: req.file.filename,
      url: `${getBaseUrl(req.get('host'))}/files/${req.file.filename}`,
    });
  });

  app.post('/wechat/parent/login', async (req, res) => {
    try {
      const openId = await resolveParentOpenId(req.body);
      const nicknameSnapshot = String(req.body?.nicknameSnapshot ?? req.body?.nickname ?? '').trim();
      const avatarUrlSnapshot = String(req.body?.avatarUrlSnapshot ?? req.body?.avatarUrl ?? '').trim();
      const payload = await loginParentWechatAccount({
        openId,
        nicknameSnapshot,
        avatarUrlSnapshot,
      });

      res.json({
        openId,
        account: payload.account,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const status = message === 'code required' ? 400 : 500;
      res.status(status).json({ error: message });
    }
  });

  app.post('/wechat/parent/bind-class', async (req, res) => {
    const inviteCode = String(req.body?.inviteCode ?? req.body?.invite_code ?? '').trim();
    const openId = String(req.body?.openId ?? req.body?.open_id ?? '').trim();
    if (!openId) {
      res.status(400).json({ error: 'openId required' });
      return;
    }
    if (!inviteCode) {
      res.status(400).json({ error: 'inviteCode required' });
      return;
    }

    try {
      const payload = await previewParentClassBinding({
        openId,
        inviteCode,
      });
      res.json(payload);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });

  app.post('/wechat/parent/bind-student', async (req, res) => {
    const openId = String(req.body?.openId ?? req.body?.open_id ?? '').trim();
    const classId = Number(req.body?.classId ?? req.body?.class_id ?? 0);
    const studentId = Number(req.body?.studentId ?? req.body?.student_id ?? 0);

    if (!openId) {
      res.status(400).json({ error: 'openId required' });
      return;
    }
    if (!Number.isFinite(classId) || classId <= 0) {
      res.status(400).json({ error: 'classId required' });
      return;
    }
    if (!Number.isFinite(studentId) || studentId <= 0) {
      res.status(400).json({ error: 'studentId required' });
      return;
    }

    try {
      const payload = await bindParentStudentOnWebsite({
        openId,
        classId,
        studentId,
      });
      res.json(payload);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });

  app.get('/wechat/parent/bindings', async (req, res) => {
    const openId = String(req.query?.openId ?? req.query?.open_id ?? '').trim();
    if (!openId) {
      res.status(400).json({ error: 'openId required' });
      return;
    }

    try {
      const payload = await listParentBindingsOnWebsite({ openId });
      res.json(payload);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });

  app.get('/wechat/parent/primary-topic-category-suggestions', async (req, res) => {
    const openId = String(req.query?.openId ?? req.query?.open_id ?? '').trim();
    const topicCategory = String(req.query?.topicCategory ?? req.query?.topic_category ?? '').trim();
    if (!openId) {
      res.status(400).json({ error: 'openId required' });
      return;
    }

    try {
      const payload = await listPrimaryTopicCategorySuggestionsOnWebsite({ openId, topicCategory });
      res.json(payload);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });

  app.post('/wechat/parent/reason-transcriptions', async (req, res) => {
    const audioUrl = String(req.body?.audioUrl ?? req.body?.audio_url ?? '').trim();
    if (!audioUrl) {
      res.status(400).json({ error: 'audioUrl required' });
      return;
    }

    res.json({ transcript_text: '语音说明已上传，老师端会继续处理。' });
  });

  app.post('/wechat/parent/reason-classifications', async (req, res) => {
    const childReasonText = String(req.body?.childReasonText ?? req.body?.child_reason_text ?? '').trim();
    if (!childReasonText) {
      res.status(400).json({ error: 'childReasonText required' });
      return;
    }

    res.json({
      display_text: childReasonText,
      primary_error_type: '',
      secondary_error_summary: '',
    });
  });

  app.post('/wechat/parent/wrong-questions', upload.single('file'), async (req, res) => {
    const openId = String(req.body?.openId ?? req.body?.open_id ?? '').trim();
    const bindingId = Number(req.body?.bindingId ?? req.body?.binding_id ?? 0);
    const childReasonText = String(req.body?.childReasonText ?? req.body?.childRawReasonText ?? req.body?.child_raw_reason_text ?? '').trim();
    const childReasonInputMode = String(req.body?.childReasonInputMode ?? req.body?.child_reason_input_mode ?? 'text').trim() || 'text';
    const childReasonAudioUrl = String(req.body?.childReasonAudioUrl ?? req.body?.child_reason_audio_url ?? '').trim();
    const topicCategory = String(req.body?.topicCategory ?? req.body?.topic_category ?? '未分类').trim() || '未分类';
    const uploadedImageUrl = req.file ? `${getBaseUrl(req.get('host'))}/files/${req.file.filename}` : '';
    const imageUrl = uploadedImageUrl || String(req.body?.imageUrl ?? req.body?.image_url ?? '').trim();

    if (!openId) {
      res.status(400).json({ error: 'openId required' });
      return;
    }
    if (!Number.isFinite(bindingId) || bindingId <= 0) {
      res.status(400).json({ error: 'bindingId required' });
      return;
    }
    if (!imageUrl) {
      res.status(400).json({ error: 'file required' });
      return;
    }
    try {
      const payload = await submitWechatWrongQuestionToWebsite({
        openId,
        bindingId,
        imageUrl,
        childReasonText,
        childReasonInputMode,
        childReasonAudioUrl,
        topicCategory,
      });
      res.status(202).json(payload);
    } catch (error) {
      sendWebsiteUploadProxyError(res, error);
    }
  });

  app.get('/wechat/parent/wrong-question-upload-tasks/:taskId', async (req, res) => {
    const openId = String(req.query?.openId ?? req.query?.open_id ?? '').trim();
    const taskId = Number(req.params.taskId);
    if (!openId) {
      res.status(400).json({ error: 'openId required' });
      return;
    }
    if (!Number.isFinite(taskId) || taskId <= 0) {
      res.status(400).json({ error: 'taskId required' });
      return;
    }

    try {
      const payload = await getWrongQuestionUploadTaskOnWebsite({ openId, taskId });
      res.json(payload);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });

  app.get('/wechat/parent/children/:studentId/wrong-questions', async (req, res) => {
    const studentId = Number(req.params.studentId);
    const openId = String(req.query?.openId ?? req.query?.open_id ?? '').trim();

    if (!Number.isFinite(studentId) || studentId <= 0) {
      res.status(400).json({ error: 'studentId required' });
      return;
    }
    if (!openId) {
      res.status(400).json({ error: 'openId required' });
      return;
    }

    try {
      const payload = await listWrongQuestionsForChildOnWebsite({ openId, studentId });
      res.json(payload);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });

  app.put('/wechat/parent/wrong-questions/:recordId/topic-category', async (req, res) => {
    const recordId = String(req.params.recordId || '').trim();
    const openId = String(req.body?.openId ?? req.body?.open_id ?? '').trim();
    const topicCategory = String(req.body?.topicCategory ?? req.body?.topic_category ?? '未分类').trim() || '未分类';

    if (!recordId) {
      res.status(400).json({ error: 'recordId required' });
      return;
    }
    if (!openId) {
      res.status(400).json({ error: 'openId required' });
      return;
    }

    try {
      const payload = await updateWrongQuestionTopicCategoryOnWebsite({ openId, recordId, topicCategory });
      res.json(payload);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });

  app.get('/wechat/parent/children/:studentId/wrong-question-library', async (req, res) => {
    const studentId = Number(req.params.studentId);
    const openId = String(req.query?.openId ?? req.query?.open_id ?? '').trim();

    if (!Number.isFinite(studentId) || studentId <= 0) {
      res.status(400).json({ error: 'studentId required' });
      return;
    }
    if (!openId) {
      res.status(400).json({ error: 'openId required' });
      return;
    }

    try {
      const payload = await getWrongQuestionLibraryForChildOnWebsite({ openId, studentId });
      res.json(payload);
    } catch (error) {
      res.status(500).json({
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });

  return app;
}

export function startServer() {
  const app = createApp();
  const server = createServer(app);
  server.listen(PORT, () => {
    console.log(`parent bridge listening on http://localhost:${PORT}`);
  });
  return server;
}

const isMainModule = process.argv[1]
  ? path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
  : false;

if (isMainModule) {
  startServer();
}
