import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService, authError, safeReturnUrl } from '../../core/auth/auth-service';
import { RuntimeConfig } from '../../core/runtime-config';

type Stage = 'login' | 'signup' | 'confirm' | 'reset' | 'reset-code' | 'new-password';

@Component({
  selector: 'app-auth-page',
  imports: [FormsModule, RouterLink],
  templateUrl: './auth-page.html',
  styleUrl: './auth-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuthPage {
  readonly auth = inject(AuthService);
  readonly config = inject(RuntimeConfig);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly stage = signal<Stage>('login');
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  email = '';
  name = '';
  password = '';
  repeatPassword = '';
  code = '';
  readonly titles: Record<Stage, string> = {
    login: 'Welcome back.', signup: 'Your adventure starts here.', confirm: 'Check your inbox.',
    reset: 'A fresh start.', 'reset-code': 'Choose a new password.', 'new-password': 'Set your permanent password.',
  };

  constructor() {
    this.route.data.pipe(takeUntilDestroyed()).subscribe(data => {
      this.stage.set(data['mode'] ?? 'login');
      this.password = ''; this.repeatPassword = ''; this.code = '';
      this.error.set(''); this.message.set('');
    });
  }

  needsPassword() { return ['login', 'signup', 'reset-code', 'new-password'].includes(this.stage()); }
  newPassword() { return this.needsPassword() && this.stage() !== 'login'; }
  needsCode() { return ['confirm', 'reset-code'].includes(this.stage()); }
  strongPassword() {
    return this.password.length >= 12 && this.password.length <= 256 &&
      /[a-z]/.test(this.password) && /[A-Z]/.test(this.password) &&
      /\d/.test(this.password) && /[^A-Za-z0-9\s]/.test(this.password);
  }

  async submit() {
    if (this.busy() || !this.auth.configured()) return;
    this.error.set(''); this.message.set('');
    if (this.newPassword() && (!this.strongPassword() || this.password !== this.repeatPassword)) {
      this.error.set('Use a matching password with at least 12 characters, uppercase, lowercase, a number and a symbol.');
      return;
    }
    this.busy.set(true);
    try {
      switch (this.stage()) {
        case 'signup': {
          const result = await this.auth.signup(this.email, this.password, this.name);
          this.stage.set(result.isSignUpComplete ? 'login' : 'confirm');
          this.message.set(result.isSignUpComplete ? 'Account created. You can now sign in.' : 'Enter the verification code sent to your email.');
          break;
        }
        case 'confirm':
          await this.auth.confirm(this.email, this.code);
          this.stage.set('login'); this.message.set('Email verified. Sign in to continue.'); break;
        case 'login':
          await this.handleSignIn(await this.auth.login(this.email, this.password)); break;
        case 'new-password':
          await this.handleSignIn(await this.auth.challenge(this.password)); break;
        case 'reset':
          await this.auth.reset(this.email); this.stage.set('reset-code');
          this.message.set('If the account is eligible, a reset code has been sent to your email.'); break;
        case 'reset-code':
          await this.auth.finishReset(this.email, this.code, this.password);
          this.stage.set('login'); this.message.set('Password updated. Sign in with your new password.'); break;
      }
    } catch (error) {
      const name = (error as { name?: string })?.name;
      if (name === 'UserNotConfirmedException') {
        this.stage.set('confirm'); this.message.set('Verify your email first. Request a new code below if needed.');
      } else if (name === 'PasswordResetRequiredException') {
        this.stage.set('reset'); this.message.set('Reset your password to continue.');
      } else this.error.set(authError(error));
    } finally {
      this.password = ''; this.repeatPassword = ''; this.code = ''; this.busy.set(false);
    }
  }

  private async handleSignIn(result: Awaited<ReturnType<AuthService['login']>>) {
    if (result.isSignedIn) {
      await this.router.navigateByUrl(safeReturnUrl(this.route.snapshot.queryParamMap.get('returnUrl')));
    } else {
      switch (result.nextStep.signInStep) {
        case 'CONFIRM_SIGN_UP': this.stage.set('confirm'); break;
        case 'RESET_PASSWORD': this.stage.set('reset'); break;
        case 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED': this.stage.set('new-password'); break;
        default: this.error.set('This account needs an authentication step that is not enabled in this app. Contact the park administrator.');
      }
    }
  }

  async resend() {
    if (this.busy() || !this.email.trim()) return;
    this.busy.set(true); this.error.set('');
    try { await this.auth.resend(this.email); this.message.set('A new verification code has been sent.'); }
    catch (error) { this.error.set(authError(error)); }
    finally { this.busy.set(false); }
  }
}
