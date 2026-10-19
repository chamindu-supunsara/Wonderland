import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { API_BASE_URL } from './api-config';
import { Attraction, TicketTier } from './catalog.models';

@Injectable({ providedIn: 'root' })
export class CatalogApi {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  attractions() {
    return this.http.get<Attraction[]>(`${this.baseUrl}/attractions`).pipe(timeout(10000));
  }

  ticketTiers() {
    return this.http.get<TicketTier[]>(`${this.baseUrl}/ticket-tiers`).pipe(timeout(10000));
  }
}
