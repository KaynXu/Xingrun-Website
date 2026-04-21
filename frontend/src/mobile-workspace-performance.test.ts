import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
const cssSource = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

test('mobile sidebar nav buttons use touch-optimized button semantics', () => {
  const sidebarBlock = source.match(/const Sidebar = \(\{[\s\S]*?\n};\n\nconst Header/);

  assert.ok(sidebarBlock);
  assert.match(sidebarBlock[0], /<button\s+type="button"/);
  assert.match(sidebarBlock[0], /touch-manipulation/);
});

test('workspace shell disables wait-mode page transitions and heavy blur on mobile', () => {
  assert.match(source, /const \[isMobileViewport, setIsMobileViewport\] = useState\(getInitialMobileViewport\);/);
  assert.match(source, /<AnimatePresence mode=\{isMobileViewport \? undefined : 'wait'\}>/);
  assert.match(source, /transition=\{isMobileViewport \? \{ duration: 0 \} : \{ duration: 0\.18 \}\}/);
  assert.match(source, /className="sticky top-0 z-10 flex h-20 items-center justify-between border-b border-sky-100\/80 bg-white\/92 px-4 sm:bg-white\/78 sm:backdrop-blur-xl/);
  assert.match(source, /className="absolute inset-0 bg-slate-950\/45 sm:backdrop-blur-sm"/);
});

test('workspace shell uses stable viewport height containers for mobile browser chrome', () => {
  assert.match(source, /<div className="relative min-h-\[100svh\] overflow-x-hidden[^\"]*sm:min-h-screen/);
  assert.match(source, /<div className="relative flex min-h-\[100svh\] sm:min-h-screen">/);
  assert.doesNotMatch(source, /<div className="relative min-h-\[100dvh\] overflow-x-hidden/);
  assert.doesNotMatch(source, /<div className="relative flex min-h-\[100dvh\]/);
  assert.doesNotMatch(source, /<div className="relative min-h-screen overflow-x-hidden bg-\[linear-gradient\(180deg,#f8fbff_0%,#eef6ff_100%\)\]/);
});

test('mobile root scrolling leaves native browser pan and overscroll behavior intact', () => {
  assert.doesNotMatch(cssSource, /body\s*\{[\s\S]*?overscroll-behavior-y:\s*(?:contain|none)/);
  assert.doesNotMatch(cssSource, /body\s*\{[\s\S]*?touch-action:/);
  assert.doesNotMatch(cssSource, /html,\s*\n\s*body\s*\{[\s\S]*?overscroll-behavior-y:\s*none/);
});

test('touch devices disable expensive filter blur during scroll', () => {
  assert.match(
    cssSource,
    /@media \(hover: none\) and \(pointer: coarse\) \{[\s\S]*\[class\^='blur-\['\],\s*\n\s*\[class\*=' blur-\['\]\s*\{[\s\S]*?filter:\s*none !important;/,
  );
});
