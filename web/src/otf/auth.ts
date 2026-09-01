/**
 * Browser-side OrangeTheory authentication via AWS Cognito SRP.
 *
 * Uses `amazon-cognito-identity-js`, which performs the USER_SRP_AUTH handshake
 * entirely in the browser and persists tokens + device key in localStorage (so
 * the user stays logged in across visits and refresh-token renewal works).
 *
 * The OTF data API authenticates with the Cognito **ID token** as
 * `Authorization: Bearer <id_token>` — see endpoints.ts.
 */

import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  type CognitoUserSession,
} from "amazon-cognito-identity-js";
import { COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID } from "./config";

const userPool = new CognitoUserPool({
  UserPoolId: COGNITO_USER_POOL_ID,
  ClientId: COGNITO_CLIENT_ID,
});

/** Identity claims extracted from the Cognito ID token. */
export interface MemberIdentity {
  /** `cognito:username` claim — the member UUID used by most OTF endpoints. */
  memberUuid: string;
  /** `sub` claim — the Cognito ID used by the body-composition endpoint. */
  cognitoId: string;
  /** `email` claim. */
  email: string;
}

function decodeJwt(token: string): Record<string, unknown> {
  const payload = token.split(".")[1];
  const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
  return JSON.parse(json) as Record<string, unknown>;
}

/** Decode member identity claims from an ID token JWT. */
export function identityFromIdToken(idToken: string): MemberIdentity {
  const claims = decodeJwt(idToken);
  return {
    memberUuid: String(claims["cognito:username"] ?? ""),
    cognitoId: String(claims["sub"] ?? ""),
    email: String(claims["email"] ?? ""),
  };
}

/**
 * Log in with email + password. Resolves once Cognito SRP completes and tokens
 * are persisted. The library transparently confirms the device so subsequent
 * refresh-token renewals succeed.
 */
export function login(email: string, password: string): Promise<MemberIdentity> {
  const cognitoUser = new CognitoUser({ Username: email, Pool: userPool });
  const authDetails = new AuthenticationDetails({ Username: email, Password: password });

  return new Promise<MemberIdentity>((resolve, reject) => {
    cognitoUser.authenticateUser(authDetails, {
      onSuccess: (session) => {
        // Persist device metadata so REFRESH_TOKEN_AUTH (which needs DEVICE_KEY)
        // works on later visits; harmless if device tracking is off.
        cognitoUser.setDeviceStatusRemembered({
          onSuccess: () => {},
          onFailure: () => {},
        });
        resolve(identityFromIdToken(session.getIdToken().getJwtToken()));
      },
      onFailure: (err) => reject(err),
      newPasswordRequired: () =>
        reject(new Error("This account requires a password reset in the OTF app before use.")),
    });
  });
}

/** True if a user session is currently stored in the browser. */
export function isLoggedIn(): boolean {
  return userPool.getCurrentUser() != null;
}

/** Current member identity from the stored session, or null if logged out. */
export async function currentIdentity(): Promise<MemberIdentity | null> {
  try {
    const token = await getValidIdToken();
    return identityFromIdToken(token);
  } catch {
    return null;
  }
}

/**
 * Return a valid (non-expired) ID token, transparently renewing it with the
 * stored refresh token + device key when needed. Rejects if no session exists or
 * renewal fails (caller should route the user back to login).
 */
export function getValidIdToken(): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const cognitoUser = userPool.getCurrentUser();
    if (!cognitoUser) {
      reject(new Error("Not logged in"));
      return;
    }
    cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session) {
        reject(err ?? new Error("No session"));
        return;
      }
      // getSession auto-refreshes via the refresh token when the access/ID token
      // has expired, so the returned token is always currently valid.
      resolve(session.getIdToken().getJwtToken());
    });
  });
}

/** Sign out and clear all stored tokens / device metadata for this browser. */
export function logout(): void {
  const cognitoUser = userPool.getCurrentUser();
  if (cognitoUser) {
    cognitoUser.signOut();
  }
}
