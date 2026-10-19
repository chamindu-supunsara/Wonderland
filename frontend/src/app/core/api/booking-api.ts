import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { timeout } from 'rxjs';
import { API_BASE_URL } from './api-config';

export interface VisitSlot {
  id: string;
  visit_date: string;
  starts_at: string;
  ends_at: string;
  capacity_guests: number;
  held_guests: number;
  confirmed_guests: number;
  remaining_guests: number;
  timezone: string;
}
export interface Booking {
  id: string;
  reference: string;
  slot_id: string;
  visit_date: string;
  starts_at: string;
  ends_at: string;
  tier_id: string;
  tier_code: string;
  tier_name: string;
  guest_count: number;
  amount_minor: number;
  currency: string;
  price_version: number;
  status: 'PENDING_PAYMENT' | 'CANCELLED' | 'EXPIRED' | 'CONFIRMED' | 'PAYMENT_FAILED';
  payment_mode?: 'NONE' | 'MOCK';
  expires_at: string;
  created_at: string;
}
export interface BookingDraft {
  tier_id: string;
  slot_id: string;
  guest_count: number;
  expected_price_version: number;
}
export interface BookingPolicy {
  today: string;
  last_date: string;
  timezone: string;
  hold_minutes: number;
}
@Injectable({ providedIn: 'root' })
export class BookingApi {
  private http = inject(HttpClient);
  private base = inject(API_BASE_URL);
  policy() {
    return this.http.get<BookingPolicy>(`${this.base}/booking-policy`).pipe(timeout(10000));
  }
  slots(date: string) {
    return this.http
      .get<VisitSlot[]>(`${this.base}/visit-slots`, { params: { date } })
      .pipe(timeout(10000));
  }
  create(body: BookingDraft, key: string) {
    return this.http
      .post<Booking>(`${this.base}/bookings`, body, { headers: { 'Idempotency-Key': key } })
      .pipe(timeout(15000));
  }
  history(offset = 0) {
    return this.http
      .get<Booking[]>(`${this.base}/bookings/me`, { params: { limit: 20, offset } })
      .pipe(timeout(10000));
  }
  detail(id: string) {
    return this.http.get<Booking>(`${this.base}/bookings/${id}`).pipe(timeout(10000));
  }
  cancel(id: string) {
    return this.http.post<Booking>(`${this.base}/bookings/${id}/cancel`, {}).pipe(timeout(10000));
  }
  addSlot(body: {
    visit_date: string;
    start_time: string;
    end_time: string;
    capacity_guests: number;
  }) {
    return this.http.post<VisitSlot>(`${this.base}/admin/visit-slots`, body).pipe(timeout(10000));
  }
}
