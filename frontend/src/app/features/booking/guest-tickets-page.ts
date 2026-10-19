import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { forkJoin, timeout } from 'rxjs';
import { API_BASE_URL } from '../../core/api/api-config';
import { Booking, BookingApi } from '../../core/api/booking-api';

export interface GuestTicket {
  id: string;
  booking_id: string;
  guest_number: number;
  reference: string;
  issued_at: string;
  is_mock: true;
}
@Component({
  selector: 'app-guest-tickets-page',
  imports: [DatePipe, RouterLink],
  templateUrl: './guest-tickets-page.html',
  styleUrls: ['./booking.scss', './guest-tickets-page.scss'],
})
export class GuestTicketsPage {
  private http = inject(HttpClient);
  private api = inject(BookingApi);
  private base = inject(API_BASE_URL);
  readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly booking = signal<Booking | null>(null);
  readonly tickets = signal<GuestTicket[]>([]);
  readonly error = signal('');
  readonly loading = signal(false);
  constructor() {
    this.load();
  }
  load() {
    this.loading.set(true);
    this.error.set('');
    forkJoin({
      booking: this.api.detail(this.id),
      tickets: this.http
        .get<GuestTicket[]>(`${this.base}/bookings/${this.id}/tickets`)
        .pipe(timeout(10000)),
    }).subscribe({
      next: (value) => {
        this.booking.set(value.booking);
        this.tickets.set(value.tickets);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(
          'Tickets are available only for your confirmed mock booking. Check your sign-in and booking status.',
        );
        this.loading.set(false);
      },
    });
  }
  print() {
    window.print();
  }
}
