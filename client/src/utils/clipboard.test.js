import assert from 'node:assert/strict';
import test from 'node:test';

import { copyTextToClipboard } from './clipboard.js';

test('uses async clipboard when available', async () => {
  const writes = [];
  const copied = await copyTextToClipboard('질문', {
    navigator: {
      clipboard: {
        async writeText(value) {
          writes.push(value);
        },
      },
    },
  });

  assert.equal(copied, true);
  assert.deepEqual(writes, ['질문']);
});

test('falls back to a textarea copy when async clipboard rejects', async () => {
  const nodes = [];
  const textarea = {
    value: '',
    style: {},
    setAttribute() {},
    select() {
      this.selected = true;
    },
    remove() {
      this.removed = true;
    },
  };
  const copied = await copyTextToClipboard('fallback', {
    navigator: {
      clipboard: {
        async writeText() {
          throw new Error('denied');
        },
      },
    },
    document: {
      body: {
        appendChild(node) {
          nodes.push(node);
        },
      },
      createElement() {
        return textarea;
      },
      execCommand(command) {
        return command === 'copy';
      },
    },
  });

  assert.equal(copied, true);
  assert.equal(textarea.value, 'fallback');
  assert.equal(textarea.selected, true);
  assert.equal(textarea.removed, true);
  assert.deepEqual(nodes, [textarea]);
});

test('returns false when no copy surface is available', async () => {
  assert.equal(await copyTextToClipboard('질문', {}), false);
});
