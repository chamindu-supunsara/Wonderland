import { PRIME_FORM_UI } from '../../shared/prime-ui';
import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AdmissionApi, RideUse, Visit } from '../../core/api/admission-api';

@Component({
  selector: 'app-visit-history',
  imports: [...PRIME_FORM_UI, DatePipe, RouterLink],
  templateUrl: './visit-history-page.html',
  styleUrl: '../booking/booking.scss',
})
export class VisitHistoryPage {
  private api = inject(AdmissionApi);
  readonly visits = signal<Visit[]>([]);
  readonly rides = signal<RideUse[]>([]);
  readonly selected = signal<string | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  offset = 0;
  rideOffset = 0;
  constructor() {
    void this.load();
  }
  async load(direction = 0) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.selected.set(null);
    const next = Math.max(0, this.offset + direction * 20);
    try {
      this.visits.set(await firstValueFrom(this.api.history(next)));
      this.offset = next;
    } catch {
      this.error.set(
        'Could not load your visits. Check sign-in and Admission service, then retry.',
      );
    } finally {
      this.busy.set(false);
    }
  }
  async showRides(id: string, direction = 0) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    const next = id === this.selected() ? Math.max(0, this.rideOffset + direction * 20) : 0;
    try {
      this.rides.set(await firstValueFrom(this.api.rides(id, next)));
      this.selected.set(id);
      this.rideOffset = next;
    } catch {
      this.error.set('Could not load ride history. Only your own guest visits are accessible.');
    } finally {
      this.busy.set(false);
    }
  }
}
