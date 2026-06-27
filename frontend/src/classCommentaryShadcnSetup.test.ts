import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { test } from 'node:test';
import { resolve } from 'node:path';

const root = resolve(
  decodeURIComponent(new URL('.', import.meta.url).pathname),
  '..'
);

test('shadcn ui is initialized for the Vite frontend', () => {
  assert.equal(existsSync(resolve(root, 'components.json')), true);
  const config = readFileSync(resolve(root, 'components.json'), 'utf8');
  assert.match(config, /"tsx": true/);
  assert.match(config, /"tailwind"/);
  assert.equal(existsSync(resolve(root, 'components/ui/button.tsx')), true);
  assert.equal(existsSync(resolve(root, 'components/ui/card.tsx')), true);
  assert.equal(existsSync(resolve(root, 'components/ui/select.tsx')), true);
});
