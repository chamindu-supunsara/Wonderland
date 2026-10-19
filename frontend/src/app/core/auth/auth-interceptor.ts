import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, switchMap } from 'rxjs';
import { API_BASE_URL } from '../api/api-config';
import { AuthService } from './auth-service';

export function isApiRequest(requestUrl: string, baseUrl: string, origin: string): boolean {
  const request = new URL(requestUrl, origin);
  const base = new URL(baseUrl, origin);
  const path = base.pathname.replace(/\/$/, '');
  return request.origin === base.origin &&
    (request.pathname === path || request.pathname.startsWith(`${path}/`));
}

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const base = inject(API_BASE_URL);
  if (!isApiRequest(request.url, base, window.location.origin)) return next(request);
  return from(auth.restore()).pipe(switchMap(token => next(token ? request.clone({
    setHeaders: { Authorization: `Bearer ${token}` },
  }) : request)));
};
