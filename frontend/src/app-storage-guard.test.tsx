import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import App from './App';

test('app still renders when auth storage access throws', () => {
  const originalLocalStorage = globalThis.localStorage;

  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem() {
        throw new Error('storage blocked');
      },
      setItem() {
        throw new Error('storage blocked');
      },
      removeItem() {
        throw new Error('storage blocked');
      },
    },
  });

  try {
    const markup = renderToStaticMarkup(<App />);
    assert.match(markup, /Starain/);
  } finally {
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: originalLocalStorage,
    });
  }
});

test('app source avoids direct auth token reads from localStorage during bootstrap', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');

  assert.doesNotMatch(source, /window\.localStorage\?\.\s*getItem\?\.\('xr_token'\)/);
});
