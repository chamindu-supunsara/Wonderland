import { computed, inject, Injectable, signal } from '@angular/core';
import { Amplify } from 'aws-amplify';
import * as cognito from 'aws-amplify/auth';
import { cognitoUserPoolsTokenProvider } from 'aws-amplify/auth/cognito';
import { sessionStorage } from 'aws-amplify/utils';
import { RuntimeConfig } from '../runtime-config';

export interface Account {
  userId: string;
  email: string;
  role: 'visitor' | 'administrator';
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly config = inject(RuntimeConfig);
  readonly user = signal<Account | null>(null);
  readonly configured = signal(false);
  readonly isAdmin = computed(() => this.user()?.role === 'administrator');

  async initialize() {
    const c = this.config.cognito;
    if (!c) return;
    Amplify.configure({ Auth: { Cognito: {
      userPoolId: c.userPoolId,
      userPoolClientId: c.userPoolClientId,
      loginWith: { email: true },
    } } });
    cognitoUserPoolsTokenProvider.setKeyValueStorage(sessionStorage);
    this.configured.set(true);
    await this.restore();
  }

  async restore(forceRefresh = false): Promise<string | null> {
    if (!this.configured()) return null;
    try {
      const session = await cognito.fetchAuthSession({ forceRefresh });
      const access = session.tokens?.accessToken;
      if (!access) { this.user.set(null); return null; }
      const groups = access.payload['cognito:groups'];
      const profile = session.tokens?.idToken?.payload;
      this.user.set({
        userId: String(access.payload.sub ?? ''),
        email: String(profile?.['email'] ?? access.payload['username'] ?? ''),
        role: Array.isArray(groups) && groups.includes('Administrators') ? 'administrator' : 'visitor',
      });
      return access.toString();
    } catch {
      this.user.set(null);
      return null;
    }
  }

  signup(email: string, password: string, name: string) {
    return cognito.signUp({ username: email.trim(), password,
      options: { userAttributes: { email: email.trim(), name: name.trim() } } });
  }
  confirm(email: string, code: string) {
    return cognito.confirmSignUp({ username: email.trim(), confirmationCode: code.trim() });
  }
  resend(email: string) { return cognito.resendSignUpCode({ username: email.trim() }); }
  async login(email: string, password: string) {
    const result = await cognito.signIn({ username: email.trim(), password });
    if (result.isSignedIn) await this.restore();
    return result;
  }
  async challenge(response: string) {
    const result = await cognito.confirmSignIn({ challengeResponse: response });
    if (result.isSignedIn) await this.restore();
    return result;
  }
  reset(email: string) { return cognito.resetPassword({ username: email.trim() }); }
  finishReset(email: string, code: string, password: string) {
    return cognito.confirmResetPassword({ username: email.trim(), confirmationCode: code.trim(), newPassword: password });
  }
  async logout() {
    try { await cognito.signOut(); } finally { this.user.set(null); }
  }
}

export function safeReturnUrl(value: string | null): string {
  return value && value.startsWith('/') && !value.startsWith('//') && !/[\\\r\n]/.test(value)
    ? value : '/account';
}

export function authError(error: unknown): string {
  const name = (error as { name?: string })?.name;
  const messages: Record<string, string> = {
    NotAuthorizedException: 'Email or password is incorrect, or your session has expired.',
    UserNotFoundException: 'Email or password is incorrect.',
    UsernameExistsException: 'An account already exists. Sign in or reset your password.',
    CodeMismatchException: 'That verification code is incorrect. Please try again.',
    ExpiredCodeException: 'That code has expired. Request a new code.',
    LimitExceededException: 'Too many attempts. Please wait before trying again.',
    TooManyRequestsException: 'Too many requests. Please wait and try again.',
    InvalidPasswordException: 'Use at least 12 characters, with uppercase, lowercase, a number and a symbol.',
    NetworkError: 'Unable to reach sign-in. Check your connection and try again.',
  };
  return messages[name ?? ''] ?? 'The request could not be completed. Please try again.';
}
