import { PRIME_FORM_UI } from '../../shared/prime-ui';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { BookingApi, BookingPolicy, VisitSlot } from '../../core/api/booking-api';
import { bookingError } from './booking-page';
@Component({
  selector: 'app-slot-admin',
  imports: [...PRIME_FORM_UI, FormsModule, RouterLink, DatePipe],
  templateUrl: './slot-admin-page.html',
  styleUrl: './booking.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SlotAdminPage {
  private api = inject(BookingApi);
  readonly policy = signal<BookingPolicy | null>(null);
  readonly slots = signal<VisitSlot[]>([]);
  readonly error = signal('');
  readonly notice = signal('');
  readonly busy = signal(false);
  date = '';
  start = '09:00';
  end = '12:00';
  capacity = 100;
  private request = 0;
  constructor() {
    void this.init();
  }
  async init() {
    try {
      const p = await firstValueFrom(this.api.policy());
      this.policy.set(p);
      this.date = p.today;
      await this.load();
    } catch (e) {
      this.error.set(bookingError(e));
    }
  }
  async load() {
    const request = ++this.request;
    this.error.set('');
    this.slots.set([]);
    try {
      const rows = await firstValueFrom(this.api.slots(this.date));
      if (request === this.request) this.slots.set(rows);
    } catch (e) {
      if (request === this.request) this.error.set(bookingError(e));
    }
  }
  async save() {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      await firstValueFrom(
        this.api.addSlot({
          visit_date: this.date,
          start_time: this.start,
          end_time: this.end,
          capacity_guests: this.capacity,
        }),
      );
      this.notice.set('Time slot added. Visitors can now reserve available guest places.');
      await this.load();
    } catch (e) {
      this.error.set(bookingError(e));
    } finally {
      this.busy.set(false);
    }
  }
}
