import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserAttribute,
  CognitoUserPool,
} from 'amazon-cognito-identity-js';

import {
  COGNITO_CLIENT_ID,
  COGNITO_USER_POOL_ID,
  cognitoConfigured,
} from './cognitoConfig';

class CognitoNotConfiguredError extends Error {
  constructor() {
    super('Cognito sign-in is not configured.');
    this.name = 'CognitoNotConfiguredError';
  }
}

const memory = new Map();

const memoryStorage = {
  setItem(key, value) {
    memory.set(key, value);
  },
  getItem(key) {
    return memory.has(key) ? memory.get(key) : null;
  },
  removeItem(key) {
    memory.delete(key);
  },
  clear() {
    memory.clear();
  },
};

let userPool = null;

function pool() {
  if (!cognitoConfigured) {
    throw new CognitoNotConfiguredError();
  }

  if (!userPool) {
    userPool = new CognitoUserPool({
      UserPoolId: COGNITO_USER_POOL_ID,
      ClientId: COGNITO_CLIENT_ID,
      Storage: memoryStorage,
    });
  }

  return userPool;
}

function normalizeEmail(email) {
  return email.trim().toLowerCase();
}

function userFor(email) {
  return new CognitoUser({
    Username: normalizeEmail(email),
    Pool: pool(),
    Storage: memoryStorage,
  });
}

export function authenticateCognito(email, password) {
  return new Promise((resolve, reject) => {
    const user = userFor(email);
    user.setAuthenticationFlowType('USER_PASSWORD_AUTH');

    const details = new AuthenticationDetails({
      Username: normalizeEmail(email),
      Password: password,
    });

    user.authenticateUser(details, {
      onSuccess(session) {
        resolve({
          user,
          idToken: session.getIdToken().getJwtToken(),
        });
      },

      onFailure(error) {
        reject(error);
      },

      newPasswordRequired() {
        reject(
          new Error(
            'This account requires a password update before sign-in can continue.',
          ),
        );
      },
    });
  });
}

export function signUpCognito(email, password) {
  const normalized = normalizeEmail(email);

  return new Promise((resolve, reject) => {
    pool().signUp(
      normalized,
      password,
      [
        new CognitoUserAttribute({
          Name: 'email',
          Value: normalized,
        }),
      ],
      null,
      (error, result) => {
        if (error) {
          reject(error);
          return;
        }

        resolve({
          user: result?.user || userFor(normalized),
          userConfirmed: Boolean(result?.userConfirmed),
        });
      },
    );
  });
}

export function confirmSignUpCognito(email, code) {
  return new Promise((resolve, reject) => {
    userFor(email).confirmRegistration(
      code.trim(),
      true,
      (error, result) => {
        if (error) {
          reject(error);
          return;
        }

        resolve(result);
      },
    );
  });
}

export function resendSignUpCodeCognito(email) {
  return new Promise((resolve, reject) => {
    userFor(email).resendConfirmationCode((error, result) => {
      if (error) {
        reject(error);
        return;
      }

      resolve(result);
    });
  });
}

export function requestPasswordResetCognito(email) {
  return new Promise((resolve, reject) => {
    userFor(email).forgotPassword({
      onSuccess(data) {
        resolve(data);
      },

      onFailure(error) {
        reject(error);
      },

      inputVerificationCode(data) {
        resolve(data);
      },
    });
  });
}

export function confirmPasswordResetCognito(
  email,
  code,
  newPassword,
) {
  return new Promise((resolve, reject) => {
    userFor(email).confirmPassword(
      code.trim(),
      newPassword,
      {
        onSuccess() {
          resolve();
        },

        onFailure(error) {
          reject(error);
        },
      },
    );
  });
}

export function clearCognitoSession() {
  try {
    pool().getCurrentUser()?.signOut();
  } catch {
    // Provider session cleanup must never prevent Ally logout.
  }

  memory.clear();
}

export { CognitoNotConfiguredError };
