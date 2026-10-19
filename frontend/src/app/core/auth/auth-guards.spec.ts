import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, provideRouter, Router, RouterStateSnapshot, UrlTree } from '@angular/router';
import { vi } from 'vitest';
import { AuthService } from './auth-service';
import { administratorGuard, signedInGuard } from './auth-guards';

describe('Protected navigation', () => {
  function setup(token: string | null, admin = false) {
    TestBed.configureTestingModule({ providers: [provideRouter([]), {
      provide: AuthService, useValue: { restore: vi.fn().mockResolvedValue(token), isAdmin: () => admin },
    }] });
  }
  const route = {} as ActivatedRouteSnapshot;
  const state = { url: '/admin' } as RouterStateSnapshot;
  it('redirects signed-out users to login with a return destination', async () => {
    setup(null);
    const result = await TestBed.runInInjectionContext(() => signedInGuard(route, state));
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/login?returnUrl=%2Fadmin');
  });
  it('blocks visitors from the admin route', async () => {
    setup('visitor-token');
    const result = await TestBed.runInInjectionContext(() => administratorGuard(route, state));
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/account?forbidden=1');
  });
  it('allows administrators after session restoration', async () => {
    setup('admin-token', true);
    expect(await TestBed.runInInjectionContext(() => administratorGuard(route, state))).toBe(true);
  });
});
