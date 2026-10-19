import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as cognito from 'aws-amplify/auth';
import { AuthService, safeReturnUrl } from './auth-service';
import { RuntimeConfig } from '../runtime-config';
import { isApiRequest } from './auth-interceptor';

vi.mock('aws-amplify', () => ({ Amplify: { configure: vi.fn() } }));
vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(), signUp: vi.fn(), signOut: vi.fn(),
}));
vi.mock('aws-amplify/auth/cognito', () => ({
  cognitoUserPoolsTokenProvider: { setKeyValueStorage: vi.fn() },
}));

describe('Cognito authentication boundaries', () => {
  let auth: AuthService;
  beforeEach(() => {
    vi.resetAllMocks();
    TestBed.configureTestingModule({ providers: [{ provide: RuntimeConfig, useValue: {
      cognito: { region: 'ap-south-1', userPoolId: 'ap-south-1_test', userPoolClientId: 'test' },
    } }] });
    auth = TestBed.inject(AuthService);
  });
  function session(groups: string[] = []) {
    return { tokens: {
      accessToken: { payload: { sub: '123', 'cognito:groups': groups }, toString: () => 'access-token' },
      idToken: { payload: { email: 'visitor@example.com' } },
    } } as unknown as Awaited<ReturnType<typeof cognito.fetchAuthSession>>;
  }
  it('defaults to visitor and only trusts the administrator group', async () => {
    vi.mocked(cognito.fetchAuthSession).mockResolvedValue(session());
    await auth.initialize();
    expect(auth.user()?.role).toBe('visitor');
    vi.mocked(cognito.fetchAuthSession).mockResolvedValue(session(['Administrators']));
    expect(await auth.restore()).toBe('access-token');
    expect(auth.isAdmin()).toBe(true);
  });
  it('clears identity when session refresh fails', async () => {
    vi.mocked(cognito.fetchAuthSession).mockResolvedValue(session(['Administrators']));
    await auth.initialize();
    vi.mocked(cognito.fetchAuthSession).mockRejectedValue(new Error('expired'));
    expect(await auth.restore()).toBeNull();
    expect(auth.user()).toBeNull();
  });
  it('signup sends no role or group attribute', async () => {
    await auth.signup(' visitor@example.com ', 'password', 'Visitor');
    expect(cognito.signUp).toHaveBeenCalledWith({ username: 'visitor@example.com', password: 'password',
      options: { userAttributes: { email: 'visitor@example.com', name: 'Visitor' } } });
  });
  it('clears identity on sign out', async () => {
    vi.mocked(cognito.fetchAuthSession).mockResolvedValue(session());
    await auth.initialize(); await auth.logout();
    expect(auth.user()).toBeNull();
  });
  it('restricts token attachment to the exact API origin and path boundary', () => {
    const origin = 'https://park.example';
    expect(isApiRequest('/api/v1/users/me', '/api/v1', origin)).toBe(true);
    expect(isApiRequest('https://evil.example/api/v1/users/me', '/api/v1', origin)).toBe(false);
    expect(isApiRequest('/api/v10/steal', '/api/v1', origin)).toBe(false);
    expect(isApiRequest('//park.example.evil/api/v1', '/api/v1', origin)).toBe(false);
    expect(isApiRequest('/app-config.json', '/api/v1', origin)).toBe(false);
  });
  it('blocks external return URLs', () => {
    for (const value of ['//evil.example', '/\\evil.example', 'https://evil.example', null]) {
      expect(safeReturnUrl(value)).toBe('/account');
    }
    expect(safeReturnUrl('/admin?view=access')).toBe('/admin?view=access');
  });
});
