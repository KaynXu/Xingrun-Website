/**
 * 文件上传处理
 * POST /upload → 保存到 uploads/ → 返回可访问的 URL
 */

import multer from 'multer';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UPLOADS_DIR = path.join(__dirname, '../../uploads');

const storage = multer.diskStorage({
  destination: UPLOADS_DIR,
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname);
    const name = `${Date.now()}-${Math.random().toString(36).slice(2)}${ext}`;
    cb(null, name);
  },
});

export const upload = multer({
  storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB
});
