import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom, timeout } from 'rxjs';
import { AuthService } from '../../core/auth/auth-service';
import { API_BASE_URL } from '../../core/api/api-config';

@Component({
  selector: 'app-account-page',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="account">
    <span class="eyebrow">WONDERLAND ACCOUNT</span>
    <h1>{{ adminPage ? 'Administrator access' : 'Hello, adventurer.' }}</h1>
    <p>{{ auth.user()?.email }}</p>
    @if (forbidden) {
      <p role="alert">
        Your account has visitor access. An administrator account is required for that page.
      </p>
    }
    <p class="role">{{ auth.user()?.role === 'administrator' ? 'Administrator' : 'Visitor' }}</p>
    <div class="verification" aria-live="polite">{{ status() }}</div>
    <button type="button" (click)="verify()" [disabled]="busy()">Check API access again</button>
    <div class="links">
      <a routerLink="/tickets">Explore tickets →</a> <a routerLink="/book">Plan a visit →</a
      ><a routerLink="/bookings">My bookings →</a><a routerLink="/visits">My visit history →</a>
      @if (auth.isAdmin() && !adminPage) {
        <a routerLink="/admin">Administrator area →</a>
      }
      @if (adminPage) {
        <a routerLink="/admin">Manage attractions and pricing →</a
        ><a routerLink="/account">My account</a>
      }
      <button type="button" (click)="logout()">Sign out</button>
    </div>
    <p class="note">
      {{
        adminPage
          ? 'Administrator identity is checked by the Python API. Open catalog management to update attractions and ticket prices.'
          : 'View your reservations and demonstration tickets in My bookings, and simulated guest check-ins and ride usage in My visit history.'
      }}
    </p>
  </section>`,
  styles: [
    `
      .account {
        max-width: 850px;
        margin: 4rem auto;
        padding: 0 2rem;
        min-height: 55vh;
      }
      h1 {
        font-size: clamp(2rem, 5vw, 4rem);
        font-weight: 500;
      }
      .eyebrow {
        font-size: 0.75rem;
        letter-spacing: 0.15em;
      }
      .role {
        display: inline-block;
        border-radius: 2rem;
        background: #f4d974;
        padding: 0.5rem 1rem;
      }
      .verification {
        padding: 1.5rem;
        background: #e7eddf;
        border-radius: 1rem;
        margin: 1rem 0;
      }
      .links {
        display: flex;
        gap: 1.5rem;
        flex-wrap: wrap;
        align-items: center;
        margin: 2rem 0;
      }
      button {
        font: inherit;
        border: 1px solid #183d31;
        border-radius: 2rem;
        padding: 0.7rem 1.2rem;
        background: transparent;
        color: #183d31;
        cursor: pointer;
      }
      button:disabled {
        opacity: 0.5;
      }
      .note {
        color: #5c6d62;
        line-height: 1.7;
      }
    `,
  ],
})
export class AccountPage {
  readonly auth = inject(AuthService);
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  readonly adminPage = this.route.snapshot.data['admin'] === true;
  readonly forbidden = this.route.snapshot.queryParamMap.has('forbidden');
  readonly status = signal('Verifying your account with the Python API…');
  readonly busy = signal(false);
  constructor() {
    void this.verify();
  }
  async verify() {
    this.busy.set(true);
    try {
      const result = await firstValueFrom(
        this.http
          .get<{ role: string }>(
            `${this.base}/${this.adminPage ? 'admin/access-check' : 'users/me'}`,
          )
          .pipe(timeout(10000)),
      );
      if (!this.adminPage && result.role === 'visitor') {
        // Check the server's role boundary with the normal authenticated client.
        try {
          await firstValueFrom(
            this.http.get(`${this.base}/admin/access-check`).pipe(timeout(10000)),
          );
          this.status.set(
            'Your account permissions need review. Administrator access was unexpectedly allowed.',
          );
        } catch (error) {
          if (!(error instanceof HttpErrorResponse) || error.status !== 403) throw error;
          this.status.set(
            'Python API verified: visitor access. Administrator access is restricted.',
          );
        }
      } else {
        this.status.set(`Python API verified: ${result.role} access.`);
      }
    } catch (error) {
      const code = error instanceof HttpErrorResponse ? error.status : 0;
      this.status.set(
        code === 403
          ? 'Access denied: administrator membership is required.'
          : code === 401
            ? 'Your session is invalid or expired. Sign out and sign in again.'
            : 'The API could not verify access. Check the backend connection and try again.',
      );
    } finally {
      this.busy.set(false);
    }
  }
  async logout() {
    await this.auth.logout();
    await this.router.navigateByUrl('/login');
  }
}
