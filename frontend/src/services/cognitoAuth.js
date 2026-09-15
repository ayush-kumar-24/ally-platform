import { clearTokens, post, setTokens } from './api';
import { setPresenceHint } from './presenceHint';
import { refreshPlanName } from '../hooks/usePlanName';
import {
  authenticateCognito,
  clearCognitoSession,
  confirmPasswordResetCognito,
  confirmSignUpCognito,
  requestPasswordResetCognito,
  resendSignUpCodeCognito,
  signUpCognito,
} from './cognitoClient';
import { cognitoConfigured } from './cognitoConfig';

export class AuthNotConfiguredError extends Error {
  constructor() {
    super('Sign-in is not configured.');
    this.name = 'AuthNotConfiguredError';
  }
}

export class AuthStepError extends Error {
  constructor(message) {
    super(message);
    this.name = 'AuthStepError';
  }
}

function translate(error, fallback) {
  const code = error?.code || error?.name || '';
  const raw = (error?.message || '').toLowerCase();

  if (
    code === 'NotAuthorizedException' ||
    raw.includes('incorrect username or password')
  ) {
    return new AuthStepError(
      'That email and password do not match. Try again, or reset your password.',
    );
  }

  if (
    code === 'UserNotConfirmedException' ||
    raw.includes('user is not confirmed')
  ) {
    return new AuthStepError(
      'Please confirm your email before signing in.',
    );
  }

  if (
    code === 'CodeMismatchException' ||
    code === 'ExpiredCodeException' ||
    raw.includes('invalid verification code') ||
    raw.includes('expired')
  ) {
    return new AuthStepError(
      'That code is wrong or has expired. Request a new one.',
    );
  }

  if (
    code === 'UsernameExistsException' ||
    raw.includes('user already exists')
  ) {
    return new AuthStepError(
      'An account already exists for this email. Sign in instead, or reset your password.',
    );
  }

  if (
    code === 'InvalidPasswordException' ||
    raw.includes('password') &&
      (raw.includes('minimum') ||
       raw.includes('uppercase') ||
       raw.includes('lowercase') ||
       raw.includes('numeric') ||
       raw.includes('symbol'))
  ) {
    return new AuthStepError(
      'That password does not meet the required password rules.',
    );
  }

  if (
    code === 'LimitExceededException' ||
    code === 'TooManyRequestsException' ||
    raw.includes('too many') ||
    raw.includes('rate')
  ) {
    return new AuthStepError(
      'Too many attempts. Please wait a minute and try again.',
    );
  }

  if (
    code === 'UserNotFoundException' ||
    raw.includes('user does not exist')
  ) {
    return new AuthStepError(
      'We could not find an account for that email.',
    );
  }

  return new AuthStepError(fallback);
}

async function exchangeForBackendSession(idToken) {
  clearTokens();

  const result = await post(
    '/auth/session',
    {},
    {
      headers: {
        Authorization: `Bearer ${idToken}`,
      },
    },
  );

  setTokens(result);
  setPresenceHint('in');

  return {
    ...result.founder,
    waitlisted: Boolean(result.waitlisted),
  };
}

async function authenticateAndExchange(email, password) {
  if (!cognitoConfigured) {
    throw new AuthNotConfiguredError();
  }

  let auth;
  try {
    auth = await authenticateCognito(email, password);
  } catch (error) {
    throw translate(
      error,
      'We could not sign you in. Please try again.',
    );
  }

  if (!auth?.idToken) {
    throw new AuthStepError(
      'Sign-in completed without an identity token. Please try again.',
    );
  }

  return exchangeForBackendSession(auth.idToken);
}

export async function signInWithPassword(email, password) {
  return authenticateAndExchange(
    email.trim().toLowerCase(),
    password,
  );
}

export async function beginSignUp(email, password) {
  if (!cognitoConfigured) {
    throw new AuthNotConfiguredError();
  }

  try {
    return await signUpCognito(
      email.trim().toLowerCase(),
      password,
    );
  } catch (error) {
    throw translate(
      error,
      "We couldn't create that account. Please try again.",
    );
  }
}

export async function confirmSignUpAndSignIn(
  email,
  code,
  password,
) {
  if (!cognitoConfigured) {
    throw new AuthNotConfiguredError();
  }

  try {
    await confirmSignUpCognito(
      email.trim().toLowerCase(),
      code,
    );
  } catch (error) {
    throw translate(
      error,
      'That code is wrong or has expired. Request a new one.',
    );
  }

  return authenticateAndExchange(
    email.trim().toLowerCase(),
    password,
  );
}

export async function resendSignUpCode(email) {
  if (!cognitoConfigured) {
    throw new AuthNotConfiguredError();
  }

  try {
    return await resendSignUpCodeCognito(
      email.trim().toLowerCase(),
    );
  } catch (error) {
    throw translate(
      error,
      "We couldn't send another code. Please try again.",
    );
  }
}

export async function beginPasswordReset(email) {
  if (!cognitoConfigured) {
    throw new AuthNotConfiguredError();
  }

  try {
    return await requestPasswordResetCognito(
      email.trim().toLowerCase(),
    );
  } catch (error) {
    throw translate(
      error,
      "We couldn't send a password reset code. Please try again.",
    );
  }
}

export async function confirmPasswordResetAndSignIn(
  email,
  code,
  newPassword,
) {
  if (!cognitoConfigured) {
    throw new AuthNotConfiguredError();
  }

  try {
    await confirmPasswordResetCognito(
      email.trim().toLowerCase(),
      code,
      newPassword,
    );
  } catch (error) {
    throw translate(
      error,
      "We couldn't reset that password. Please try again.",
    );
  }

  return authenticateAndExchange(
    email.trim().toLowerCase(),
    newPassword,
  );
}

export async function logout() {
  try {
    await post('/auth/logout');
  } catch {
    // Local cleanup must still happen if server-side revocation fails.
  } finally {
    clearTokens();
    clearCognitoSession();
    setPresenceHint('out');
    localStorage.removeItem('ally_founder');
    refreshPlanName();
  }
}

export async function startDevSession() {
  const token = import.meta.env.VITE_DEV_FOUNDER_TOKEN;
  if (!token) return null;

  clearTokens();

  const result = await post(
    '/auth/session',
    {},
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  setTokens(result);
  setPresenceHint('in');

  return result.founder;
}
