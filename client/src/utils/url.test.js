import assert from 'node:assert/strict';
import test from 'node:test';

import { normalizeArticleInput } from './url.js';

test('adds https to a scheme-less article URL', () => {
  assert.equal(normalizeArticleInput(' example.com/article '), 'https://example.com/article');
});

test('preserves an explicit HTTP URL', () => {
  assert.equal(normalizeArticleInput('http://example.com/article'), 'http://example.com/article');
});

test('rejects unsupported URL schemes', () => {
  assert.throws(() => normalizeArticleInput('file:///etc/passwd'), /HTTP/);
});

test('rejects blank input', () => {
  assert.throws(() => normalizeArticleInput('   '), /입력/);
});
