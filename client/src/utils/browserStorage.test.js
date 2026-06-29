import assert from 'node:assert/strict';
import test from 'node:test';

import { createSafeStorage } from './browserStorage.js';

test('safe storage returns the fallback when reads throw', () => {
  const storage = createSafeStorage({
    getItem() {
      throw new Error('blocked');
    },
  });

  assert.equal(storage.getItem('reader-target-url', ''), '');
});

test('safe storage ignores write failures', () => {
  const storage = createSafeStorage({
    setItem() {
      throw new Error('quota');
    },
  });

  assert.equal(storage.setItem('reader-target-url', 'https://example.com'), false);
});

test('safe storage parses JSON with fallback on invalid data', () => {
  const storage = createSafeStorage({
    getItem() {
      return '{broken';
    },
  });

  assert.deepEqual(storage.getJson('reader-settings', { fontSize: 18 }), { fontSize: 18 });
});
