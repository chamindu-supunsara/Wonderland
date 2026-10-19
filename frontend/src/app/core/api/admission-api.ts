import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { timeout } from 'rxjs';
import { API_BASE_URL } from './api-config';

export interface AdmissionTicket {
  id: string;
  reference: string;
  booking_id: string;
  booking_reference: string;
  guest_number: number;
  tier_code: string;
  tier_name: string;
  starts_at: string;
  ends_at: string;
}
export interface Visit {
  id: string;
  ticket: AdmissionTicket;
  occurred_at: string;
  recorded_at: string;
  ride_count: number;
  mode: 'MOCK';
  already_checked_in?: boolean;
}
export interface RideUse {
  id: string;
  attraction_id: string;
  attraction_name: string;
  category: string;
  occurred_at: string;
  recorded_at: string;
  mode: 'MOCK';
}
export interface TicketLookup {
  ticket: AdmissionTicket;
  check_in: Visit | null;
  recent_rides: RideUse[];
  mode: 'MOCK';
}
export interface CheckInDraft {
  ticket_reference: string;
  simulation_time: string;
}
export interface RideDraft extends CheckInDraft {
  attraction_id: string;
}
@Injectable({ providedIn: 'root' })
export class AdmissionApi {
  private http = inject(HttpClient);
  private base = inject(API_BASE_URL) + '/admissions';
  lookup(reference: string) {
    return this.http
      .get<TicketLookup>(`${this.base}/staff/tickets/${encodeURIComponent(reference)}`)
      .pipe(timeout(15000));
  }
  checkIn(body: CheckInDraft) {
    return this.http.post<Visit>(`${this.base}/staff/check-ins`, body).pipe(timeout(15000));
  }
  ride(body: RideDraft, key: string) {
    return this.http
      .post<RideUse>(`${this.base}/staff/ride-uses`, body, { headers: { 'Idempotency-Key': key } })
      .pipe(timeout(15000));
  }
  history(offset = 0) {
    return this.http
      .get<Visit[]>(`${this.base}/visits/me`, { params: { limit: 20, offset } })
      .pipe(timeout(10000));
  }
  rides(id: string, offset = 0) {
    return this.http
      .get<RideUse[]>(`${this.base}/visits/${id}/rides`, { params: { limit: 20, offset } })
      .pipe(timeout(10000));
  }
}
