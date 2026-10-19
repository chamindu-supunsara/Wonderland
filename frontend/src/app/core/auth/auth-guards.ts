import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth-service';

export const signedInGuard: CanActivateFn = async (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return await auth.restore() ? true : router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

export const administratorGuard: CanActivateFn = async (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!await auth.restore()) return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
  return auth.isAdmin() ? true : router.createUrlTree(['/account'], { queryParams: { forbidden: '1' } });
};
