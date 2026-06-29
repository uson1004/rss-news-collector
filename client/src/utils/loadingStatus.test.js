import assert from 'node:assert/strict';
import test from 'node:test';

import { hasLoadingStatus } from './loadingStatus.js';

test('detects whether any status is loading', () => {
  assert.equal(hasLoadingStatus(['idle', 'success', 'loading']), true);
  assert.equal(hasLoadingStatus(['idle', 'error', 'success']), false);
});

test('ignores empty or non-array status collections', () => {
  assert.equal(hasLoadingStatus([]), false);
  assert.equal(hasLoadingStatus(null), false);
});
