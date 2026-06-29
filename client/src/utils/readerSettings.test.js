import assert from 'node:assert/strict';
import test from 'node:test';

import { normalizeReaderSettings } from './readerSettings.js';

const defaults = {
  fontSize: 18,
  lineHeight: 1.75,
  paragraphSpacing: 1.4,
  contentWidth: 720,
  theme: 'light',
};

test('normalizes stored reader settings into supported ranges', () => {
  assert.deepEqual(
    normalizeReaderSettings(
      {
        fontSize: 999,
        lineHeight: 0.2,
        paragraphSpacing: 'wide',
        contentWidth: 120,
        theme: 'solarized',
      },
      defaults,
    ),
    {
      fontSize: 24,
      lineHeight: 1.45,
      paragraphSpacing: 1.4,
      contentWidth: 560,
      theme: 'light',
    },
  );
});

test('keeps valid reader settings', () => {
  assert.deepEqual(
    normalizeReaderSettings(
      {
        fontSize: 20,
        lineHeight: 1.9,
        paragraphSpacing: 1.8,
        contentWidth: 760,
        theme: 'contrast',
      },
      defaults,
    ),
    {
      fontSize: 20,
      lineHeight: 1.9,
      paragraphSpacing: 1.8,
      contentWidth: 760,
      theme: 'contrast',
    },
  );
});
