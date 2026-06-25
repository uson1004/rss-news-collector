import assert from 'node:assert/strict';
import test from 'node:test';

import { getReaderRecoveryOptions } from './readerRecovery.js';

test('offers retry when a reader target is available', () => {
  assert.deepEqual(getReaderRecoveryOptions(true), [
    { id: 'retry', label: '다시 시도' },
    { id: 'url', label: '다른 URL 입력', route: '/url' },
    { id: 'news', label: '뉴스로 돌아가기', route: '/news' },
  ]);
});

test('omits retry when no reader target is available', () => {
  assert.deepEqual(getReaderRecoveryOptions(false).map((option) => option.id), ['url', 'news']);
});
