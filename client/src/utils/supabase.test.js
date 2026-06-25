import assert from 'node:assert/strict';
import test from 'node:test';

import { createOptionalSupabaseClient } from './supabase.js';

test('returns no client when Supabase credentials are missing', () => {
  let factoryCalled = false;
  const result = createOptionalSupabaseClient({}, () => {
    factoryCalled = true;
  });

  assert.equal(result.client, null);
  assert.equal(result.configured, false);
  assert.equal(factoryCalled, false);
});

test('creates a client when both Supabase credentials exist', () => {
  const expectedClient = { from() {} };
  const result = createOptionalSupabaseClient(
    {
      VITE_SUPABASE_URL: 'https://project.supabase.co',
      VITE_SUPABASE_PUBLISHABLE_KEY: 'publishable-key',
    },
    (url, key) => {
      assert.equal(url, 'https://project.supabase.co');
      assert.equal(key, 'publishable-key');
      return expectedClient;
    },
  );

  assert.equal(result.client, expectedClient);
  assert.equal(result.configured, true);
});
