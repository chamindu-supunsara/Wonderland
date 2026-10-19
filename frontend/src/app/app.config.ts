import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { RuntimeConfig } from './core/runtime-config';
import { AuthService } from './core/auth/auth-service';
import { authInterceptor } from './core/auth/auth-interceptor';

import { routes } from './app.routes';
import { providePrimeNG } from 'primeng/config';
import { WonderlandTheme } from './shared/wonderland-theme';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    providePrimeNG({
      ripple: false,
      theme: { preset: WonderlandTheme, options: { darkModeSelector: false } },
    }),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAppInitializer(() => {
      const config = inject(RuntimeConfig);
      const auth = inject(AuthService);
      return config.load().then(() => auth.initialize());
    }),
  ],
};
