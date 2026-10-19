import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { API_BASE_URL } from './api-config';
import { Attraction, TicketTier } from './catalog.models';

export type AttractionDraft = Omit<Attraction, 'id'>;
export interface AdminAttraction extends Attraction {
  status: 'ACTIVE' | 'RETIRED';
  revision: number;
  created_at: string;
  updated_at: string;
}
export interface AdminTier extends TicketTier {
  active: boolean;
}
export interface PriceVersion {
  id: string;
  amount_minor: number;
  currency: string;
  version: number;
  active: boolean;
  created_at: string;
  created_by: string | null;
}
export interface AuditEvent {
  id: string;
  actor_id: string;
  action: string;
  resource_id: string;
  created_at: string;
  changes: { before: unknown; after: unknown };
}

@Injectable({ providedIn: 'root' })
export class AdminApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/admin`;
  attractions() {
    return this.http.get<AdminAttraction[]>(`${this.base}/attractions`).pipe(timeout(10000));
  }
  create(body: AttractionDraft) {
    return this.http.post<AdminAttraction>(`${this.base}/attractions`, body).pipe(timeout(15000));
  }
  update(ride: AdminAttraction, body: AttractionDraft) {
    return this.http
      .put<AdminAttraction>(`${this.base}/attractions/${ride.id}`, {
        ...body,
        expected_revision: ride.revision,
      })
      .pipe(timeout(15000));
  }
  retire(ride: AdminAttraction) {
    return this.http
      .post<AdminAttraction>(`${this.base}/attractions/${ride.id}/retire`, {
        expected_revision: ride.revision,
      })
      .pipe(timeout(15000));
  }
  tiers() {
    return this.http.get<AdminTier[]>(`${this.base}/ticket-tiers`).pipe(timeout(10000));
  }
  history(id: string) {
    return this.http
      .get<PriceVersion[]>(`${this.base}/ticket-tiers/${id}/prices`)
      .pipe(timeout(10000));
  }
  publish(tier: AdminTier, amount: number) {
    return this.http
      .post<PriceVersion>(`${this.base}/ticket-tiers/${tier.id}/prices`, {
        amount_minor: amount,
        expected_version: tier.price_version,
      })
      .pipe(timeout(15000));
  }
  audit() {
    return this.http.get<AuditEvent[]>(`${this.base}/audit`).pipe(timeout(10000));
  }
}

export function parsePrice(value: string): number | null {
  const match = /^(\d{1,7})(?:\.(\d{1,2}))?$/.exec(value.trim());
  if (!match) return null;
  const amount = Number(match[1]) * 100 + Number((match[2] ?? '').padEnd(2, '0'));
  return amount >= 1 && amount <= 100_000_000 ? amount : null;
}
