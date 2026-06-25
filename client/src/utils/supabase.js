import { createClient } from '@supabase/supabase-js';

export function createOptionalSupabaseClient(environment, clientFactory = createClient) {
  const supabaseUrl = environment.VITE_SUPABASE_URL;
  const supabaseKey = environment.VITE_SUPABASE_PUBLISHABLE_KEY;

  if (!supabaseUrl || !supabaseKey) {
    return { client: null, configured: false };
  }

  return {
    client: clientFactory(supabaseUrl, supabaseKey),
    configured: true,
  };
}

const optionalSupabase = createOptionalSupabaseClient(import.meta.env ?? {});

export const supabase = optionalSupabase.client;
export const supabaseConfigured = optionalSupabase.configured;
