import { readFile } from 'node:fs/promises';

import { buildWrongQuestionLatexPreviewModel } from '../src/wrongQuestionLatex.js';

const payloadPath = process.argv[2];

if (!payloadPath) {
  console.error('payload path is required');
  process.exit(2);
}

const payload = JSON.parse(await readFile(payloadPath, 'utf8'));
const preview = buildWrongQuestionLatexPreviewModel(payload.questionText || '');

process.stdout.write(JSON.stringify({
  errors: preview.errors.map((error) => ({
    type: error.type || '',
    source: error.source || '',
    message: error.message || '公式渲染失败',
  })),
}));
