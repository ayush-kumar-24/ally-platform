import { cognitoConfigured } from './cognitoConfig';
import { supabaseConfigured } from './supabaseConfig';

const requestedProvider = (
  import.meta.env.VITE_AUTH_PROVIDER || 'supabase'
).trim().toLowerCase();

export const authProvider =
  requestedProvider === 'cognito' ? 'cognito' : 'supabase';

export const usingCognitoAuth = authProvider === 'cognito';
export const usingSupabaseAuth = authProvider === 'supabase';

export const authConfigured = usingCognitoAuth
  ? cognitoConfigured
  : supabaseConfigured;
