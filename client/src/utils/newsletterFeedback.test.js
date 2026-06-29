import assert from 'node:assert/strict';
import test from 'node:test';

import { clearedNewsletterFeedback } from './newsletterFeedback.js';

test('returns the idle newsletter feedback state', () => {
  assert.deepEqual(clearedNewsletterFeedback(), {
    status: 'idle',
    error: '',
    message: '',
  });
});
