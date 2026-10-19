import { PRIME_FORM_UI } from '../../shared/prime-ui';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { Booking, BookingApi } from '../../core/api/booking-api';
import { bookingError } from './booking-page';
@Component({
  selector: 'app-history-page',
  imports: [...PRIME_FORM_UI, CurrencyPipe, DatePipe, RouterLink],
  templateUrl: './history-page.html',
  styleUrl: './booking.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HistoryPage {
  private api = inject(BookingApi);
  private route = inject(ActivatedRoute);
  readonly rows = signal<Booking[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly confirm = signal<string | null>(null);
  readonly id = this.route.snapshot.paramMap.get('id');
  offset = 0;
  constructor() {
    void this.load();
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      this.rows.set(
        this.id
          ? [await firstValueFrom(this.api.detail(this.id))]
          : await firstValueFrom(this.api.history(this.offset)),
      );
    } catch (e) {
      this.error.set(bookingError(e));
    } finally {
      this.loading.set(false);
    }
  }
  async cancel(id: string) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(this.api.cancel(id));
      this.confirm.set(null);
      await this.load();
    } catch (e) {
      this.error.set(bookingError(e));
    } finally {
      this.busy.set(false);
    }
  }
  page(direction: number) {
    this.offset = Math.max(0, this.offset + direction * 20);
    void this.load();
  }
}
