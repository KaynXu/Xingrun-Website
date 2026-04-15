const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const BACKEND_DIR = __dirname;

test('backend keeps only parent bridge source files and removes legacy chat dependencies', () => {
  for (const file of [
    'src/feedback.ts',
    'src/openclaw.ts',
    'src/roster.ts',
    'src/rooms.ts',
    'src/scheduler.ts',
    'src/subscription.ts',
    'src/teacher-records.test.ts',
    'src/vision.ts',
    'test-pdf.ts',
    'scripts/import-roster.mjs',
  ]) {
    assert.equal(fs.existsSync(path.join(BACKEND_DIR, file)), false, `${file} should be removed`);
  }

  const packageJson = JSON.parse(fs.readFileSync(path.join(BACKEND_DIR, 'package.json'), 'utf8'));
  assert.equal('ws' in packageJson.dependencies, false);
  assert.equal('pdfkit' in packageJson.dependencies, false);
  assert.equal('xlsx' in packageJson.dependencies, false);
  assert.equal('import:roster' in packageJson.scripts, false);
});
