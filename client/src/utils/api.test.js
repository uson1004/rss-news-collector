import assert from 'node:assert/strict';
import test from 'node:test';

import { requestJson } from './api.js';

test('uses the API detail from a JSON error response', async () => {
  await assert.rejects(
    requestJson(
      '/api/example',
      {},
      '기본 오류',
      async () =>
        new Response(JSON.stringify({ detail: '구체적인 오류' }), {
          status: 422,
          headers: { 'Content-Type': 'application/json' },
        }),
    ),
    /구체적인 오류/,
  );
});

test('uses the fallback message for an HTML error response', async () => {
  await assert.rejects(
    requestJson(
      '/api/example',
      {},
      '요청을 처리하지 못했어요.',
      async () => new Response('<html>Bad gateway</html>', { status: 502 }),
    ),
    /요청을 처리하지 못했어요/,
  );
});

test('reports malformed JSON from a successful response', async () => {
  await assert.rejects(
    requestJson('/api/example', {}, '기본 오류', async () => new Response('{broken', { status: 200 })),
    /서버 응답을 읽지 못했어요/,
  );
});

test('returns null for an empty successful response', async () => {
  const result = await requestJson('/api/example', {}, '기본 오류', async () => new Response(null, { status: 204 }));

  assert.equal(result, null);
});
