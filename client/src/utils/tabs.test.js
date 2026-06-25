import assert from 'node:assert/strict';
import test from 'node:test';

import { getNextTabIndex } from './tabs.js';

test('wraps arrow navigation across the tab list', () => {
  assert.equal(getNextTabIndex(0, 'ArrowLeft', 4), 3);
  assert.equal(getNextTabIndex(3, 'ArrowRight', 4), 0);
});

test('supports Home and End navigation', () => {
  assert.equal(getNextTabIndex(2, 'Home', 4), 0);
  assert.equal(getNextTabIndex(1, 'End', 4), 3);
});

test('keeps the current tab for unrelated keys or an empty list', () => {
  assert.equal(getNextTabIndex(2, 'Enter', 4), 2);
  assert.equal(getNextTabIndex(0, 'ArrowRight', 0), 0);
});
