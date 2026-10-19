import { inject, InjectionToken } from '@angular/core';
import { RuntimeConfig } from '../runtime-config';

// Development uses the Angular proxy. Supply the gateway base URL at cloud deployment.
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  providedIn: 'root',
  factory: () => inject(RuntimeConfig).apiBaseUrl,
});
