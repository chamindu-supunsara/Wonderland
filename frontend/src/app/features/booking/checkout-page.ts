import { PRIME_FORM_UI } from '../../shared/prime-ui';
import { Component, inject, signal } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { API_BASE_URL } from '../../core/api/api-config';
import { timeout } from 'rxjs';

export interface Checkout {
  id: string;
  booking_id: string;
  booking_reference: string;
  amount_minor: number;
  currency: string;
  status: 'READY' | 'DECIDED' | 'SUCCEEDED' | 'FAILED' | 'REJECTED';
  outcome: 'success' | 'failure' | null;
  mode: 'MOCK';
}
@Component({
  selector: 'app-checkout-page',
  imports: [...PRIME_FORM_UI, CurrencyPipe, RouterLink],
  templateUrl: './checkout-page.html',
  styleUrl: './booking.scss',
})
export class CheckoutPage {
  private http = inject(HttpClient);
  private base = inject(API_BASE_URL);
  readonly bookingId = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly checkout = signal<Checkout | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  // Retain the selected outcome even when the response is lost. Reload restores it from Python.
  readonly chosen = signal<'success' | 'failure' | null>(null);
  constructor() {
    this.load();
  }
  load() {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.http
      .post<Checkout>(`${this.base}/payments/checkouts`, { booking_id: this.bookingId })
      .pipe(timeout(15000))
      .subscribe({
        next: (row) => {
          this.checkout.set(row);
          this.chosen.set(row.outcome);
          this.busy.set(false);
        },
        error: () => {
          this.error.set(
            'Could not load checkout. Check your sign-in and reservation status, then retry.',
          );
          this.busy.set(false);
        },
      });
  }
  complete(outcome: 'success' | 'failure') {
    const row = this.checkout();
    if (!row || this.busy() || (this.chosen() && this.chosen() !== outcome)) return;
    this.chosen.set(outcome);
    this.busy.set(true);
    this.error.set('');
    this.http
      .post<Checkout>(`${this.base}/payments/checkouts/${row.id}/complete`, { outcome })
      .pipe(timeout(15000))
      .subscribe({
        next: (result) => {
          this.checkout.set(result);
          this.busy.set(false);
        },
        error: () => {
          this.error.set(
            'The result is not yet verified. Check your sign-in, then retry the SAME simulation.',
          );
          this.busy.set(false);
        },
      });
  }
}
