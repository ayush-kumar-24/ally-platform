export const COGNITO_REGION =
  import.meta.env.VITE_COGNITO_REGION || '';

export const COGNITO_USER_POOL_ID =
  import.meta.env.VITE_COGNITO_USER_POOL_ID || '';

export const COGNITO_CLIENT_ID =
  import.meta.env.VITE_COGNITO_CLIENT_ID || '';

export const cognitoConfigured = Boolean(
  COGNITO_REGION &&
  COGNITO_USER_POOL_ID &&
  COGNITO_CLIENT_ID
);
