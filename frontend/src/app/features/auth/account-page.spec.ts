import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { API_BASE_URL } from '../../core/api/api-config';
import { AuthService } from '../../core/auth/auth-service';
import { AccountPage } from './account-page';

describe('Account permission verification', () => {
  let http: HttpTestingController;
  function setup() {
    TestBed.configureTestingModule({
      imports: [AccountPage],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: '/api/v1' },
        {
          provide: AuthService,
          useValue: {
            user: () => ({ email: 'visitor@example.test', role: 'visitor' }),
            isAdmin: () => false,
          },
        },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { data: {}, queryParamMap: convertToParamMap({}) } },
        },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    return TestBed.createComponent(AccountPage).componentInstance;
  }
  afterEach(() => http.verify());
  it('confirms a visitor only after the backend rejects administrator access', async () => {
    const page = setup();
    http.expectOne('/api/v1/users/me').flush({ role: 'visitor' });
    await Promise.resolve();
    http
      .expectOne('/api/v1/admin/access-check')
      .flush({ detail: 'Forbidden' }, { status: 403, statusText: 'Forbidden' });
    await Promise.resolve();
    expect(page.status()).toContain('visitor access. Administrator access is restricted.');
  });
  it('reports unexpected administrator access instead of claiming a correct visitor boundary', async () => {
    const page = setup();
    http.expectOne('/api/v1/users/me').flush({ role: 'visitor' });
    await Promise.resolve();
    http.expectOne('/api/v1/admin/access-check').flush({ role: 'administrator' });
    await Promise.resolve();
    expect(page.status()).toContain('permissions need review');
  });
  it('does not mistake an expired token for a successful role denial', async () => {
    const page = setup();
    http.expectOne('/api/v1/users/me').flush({ role: 'visitor' });
    await Promise.resolve();
    http
      .expectOne('/api/v1/admin/access-check')
      .flush({ detail: 'Unauthorized' }, { status: 401, statusText: 'Unauthorized' });
    await Promise.resolve();
    expect(page.status()).toContain('session is invalid or expired');
  });
});
