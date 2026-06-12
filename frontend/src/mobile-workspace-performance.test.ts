import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
const sidebarSource = readFileSync(resolve(process.cwd(), 'src/features/navigation/Sidebar.tsx'), 'utf8');
const headerSource = readFileSync(resolve(process.cwd(), 'src/features/navigation/Header.tsx'), 'utf8');
const shellSource = readFileSync(resolve(process.cwd(), 'src/features/navigation/WorkspaceShellLayout.tsx'), 'utf8');
const cssSource = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');
const courseCalendarSource = readFileSync(resolve(process.cwd(), 'src/CourseCalendarPage.tsx'), 'utf8');
const smartWrongQuestionsSource = readFileSync(resolve(process.cwd(), 'src/SmartWrongQuestionsPage.tsx'), 'utf8');

test('mobile sidebar nav buttons use touch-optimized button semantics', () => {
  const sidebarBlock = sidebarSource.match(/export function Sidebar\([\s\S]*?\n}\n/);

  assert.ok(sidebarBlock);
  assert.match(sidebarBlock[0], /<button\s+type="button"/);
  assert.match(sidebarBlock[0], /touch-manipulation/);
});

test('workspace shell disables wait-mode page transitions and heavy blur on mobile', () => {
  assert.match(source, /const \[isMobileViewport, setIsMobileViewport\] = useState\(getInitialMobileViewport\);/);
  assert.match(source, /<AnimatePresence mode=\{isMobileViewport \? undefined : 'wait'\}>/);
  assert.match(source, /transition=\{isMobileViewport \? \{ duration: 0 \} : \{ duration: 0\.18 \}\}/);
  assert.match(headerSource, /className="sticky top-0 z-10 flex h-20 items-center justify-end border-b border-sky-100\/80 bg-white\/92 px-4 sm:bg-white\/78 sm:backdrop-blur-xl/);
  assert.doesNotMatch(source, /<p className="text-xs font-semibold uppercase tracking-\[0\.28em\] text-sky-600">Workspace<\/p>/);
  assert.match(shellSource, /className="absolute inset-0 bg-slate-950\/45 sm:backdrop-blur-sm"/);
});

test('workspace shell uses stable viewport height containers for mobile browser chrome', () => {
  assert.match(shellSource, /<div className="relative min-h-\[100svh\] overflow-x-hidden[^\"]*sm:min-h-screen/);
  assert.match(shellSource, /<div className="relative flex min-h-\[100svh\] sm:min-h-screen">/);
  assert.doesNotMatch(shellSource, /<div className="relative min-h-\[100dvh\] overflow-x-hidden/);
  assert.doesNotMatch(shellSource, /<div className="relative flex min-h-\[100dvh\]/);
  assert.doesNotMatch(shellSource, /<div className="relative min-h-screen overflow-x-hidden bg-\[linear-gradient\(180deg,#f8fbff_0%,#eef6ff_100%\)\]/);
});

test('workspace shell keeps authenticated content on native page scroll', () => {
  const shellBlock = shellSource.match(/<div className="relative flex min-h-\[100svh\] sm:min-h-screen">[\s\S]*?<\/main>\n\s*<\/div>\n\s*<\/div>\n\s*\);\n}/);

  assert.ok(shellBlock);
  assert.match(shellBlock[0], /<main className=\{cn\('flex min-w-0 flex-1 flex-col'/);
  assert.match(shellBlock[0], /<div className="flex-1">/);
  assert.doesNotMatch(shellBlock[0], /<main[^>]*overflow-y-auto/);
  assert.doesNotMatch(shellBlock[0], /<main[^>]*overscroll-/);
  assert.doesNotMatch(shellBlock[0], /<div className="flex-1 overflow-y-auto"/);
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

test('course calendar tall mobile page avoids full-screen nested scroll and horizontal overflow controls', () => {
  assert.match(courseCalendarSource, /<div className="min-h-full/);
  assert.match(courseCalendarSource, /<div className="space-y-4 lg:hidden">/);
  assert.match(courseCalendarSource, /inline-flex w-full min-w-0 items-center gap-2 rounded-2xl/);
  assert.match(courseCalendarSource, /className="min-w-0 flex-1 px-2 text-center sm:min-w-72"/);
  assert.doesNotMatch(courseCalendarSource, /<div className="min-h-screen/);
  assert.doesNotMatch(courseCalendarSource, /<div className="min-h-\[100(?:dvh|svh)\]/);
  assert.doesNotMatch(courseCalendarSource, /lg:hidden[\s\S]{0,600}overflow-y-auto/);
});

test('smart wrong questions tall page keeps nested scrolling inside the intentional notebook modal', () => {
  const pageBeforeModal = smartWrongQuestionsSource.match(/return \(\n\s*<div className=\{`\$\{workspacePageClass\} space-y-8`\}>[\s\S]*?\n\s*\{selectedStudentName && \(/);

  assert.ok(pageBeforeModal);
  assert.doesNotMatch(pageBeforeModal[0], /overflow-y-auto/);
  assert.match(smartWrongQuestionsSource, /className="fixed inset-0 z-50 flex items-center justify-center/);
  assert.match(smartWrongQuestionsSource, /max-h-\[92vh\]/);
  assert.match(smartWrongQuestionsSource, /min-h-0 overflow-y-auto/);
});
