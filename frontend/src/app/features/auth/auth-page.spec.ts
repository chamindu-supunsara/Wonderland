import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { vi } from 'vitest';
import { AuthPage } from './auth-page';
import { AuthService } from '../../core/auth/auth-service';

describe('Account forms', () => {
  it('rejects mismatched passwords before calling Cognito', async () => {
    const signup = vi.fn();
    TestBed.configureTestingModule({ providers: [provideRouter([]), {
      provide: AuthService, useValue: { configured: signal(true), signup },
    }] });
    const fixture = TestBed.createComponent(AuthPage);
    const page = fixture.componentInstance;
    page.stage.set('signup'); page.email = 'visitor@example.com'; page.name = 'Visitor';
    page.password = 'ValidPassword123!'; page.repeatPassword = 'DifferentPassword123!';
    await page.submit(); fixture.detectChanges();
    expect(signup).not.toHaveBeenCalled();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('matching');
  });
  it('moves signup to email confirmation and clears the password', async () => {
    const signup = vi.fn().mockResolvedValue({ isSignUpComplete: false });
    TestBed.configureTestingModule({ providers: [provideRouter([]), {
      provide: AuthService, useValue: { configured: signal(true), signup },
    }] });
    const page = TestBed.createComponent(AuthPage).componentInstance;
    page.stage.set('signup'); page.email = 'visitor@example.com'; page.name = 'Visitor';
    page.password = page.repeatPassword = 'ValidPassword123!';
    await page.submit();
    expect(page.stage()).toBe('confirm'); expect(page.password).toBe('');
    expect(signup).toHaveBeenCalledOnce();
  });
});
