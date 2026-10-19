import { Injectable } from '@angular/core';

export interface CognitoConfig {
  region: string;
  userPoolId: string;
  userPoolClientId: string;
}

@Injectable({ providedIn: 'root' })
export class RuntimeConfig {
  apiBaseUrl = '/api/v1';
  cognito: CognitoConfig | null = null;
  error = '';

  async load() {
    try {
      const response = await fetch('/app-config.json', { cache: 'no-store' });
      if (!response.ok) throw new Error('Configuration unavailable');
      const value = await response.json();
      const api = new URL(value.apiBaseUrl, window.location.origin);
      if (api.username || api.password || api.search || api.hash ||
          !['http:', 'https:'].includes(api.protocol)) throw new Error('Invalid API URL');
      this.apiBaseUrl = api.href.replace(/\/$/, '');
      if (value.cognito) {
        const c = value.cognito;
        if (!/^[a-z]{2}-[a-z]+-\d$/.test(c.region) ||
            !new RegExp(`^${c.region}_[A-Za-z0-9]+$`).test(c.userPoolId) ||
            !/^[a-z0-9]{1,128}$/.test(c.userPoolClientId)) throw new Error('Invalid Cognito configuration');
        this.cognito = c;
      }
    } catch {
      this.error = 'Account setup is unavailable. Check app-config.json and reload.';
      this.cognito = null;
    }
  }
}
