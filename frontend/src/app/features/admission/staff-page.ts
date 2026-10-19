import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AdmissionApi, RideDraft, TicketLookup } from '../../core/api/admission-api';
import { CatalogApi } from '../../core/api/catalog-api';
import { Attraction } from '../../core/api/catalog.models';
import { AuthService } from '../../core/auth/auth-service';

@Component({
  selector: 'app-staff-admission',
  imports: [FormsModule, RouterLink, DatePipe],
  templateUrl: './staff-page.html',
  styleUrl: '../booking/booking.scss',
})
export class StaffAdmissionPage {
  private api = inject(AdmissionApi);
  private catalog = inject(CatalogApi);
  private retryStorageKey = 'wonderland-mock-ride:' + inject(AuthService).user()?.userId;
  reference = '';
  simulationTime = '';
  attractionId = '';
  readonly lookup = signal<TicketLookup | null>(null);
  readonly attractions = signal<Attraction[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly catalogError = signal('');
  readonly notice = signal('');
  readonly pending = signal<{ body: RideDraft; key: string } | null>(null);
  constructor() {
    void this.loadAttractions();
    try {
      const raw = sessionStorage.getItem(this.retryStorageKey);
      if (raw) {
        const saved = JSON.parse(raw);
        if (
          typeof saved.key === 'string' &&
          typeof saved.body?.ticket_reference === 'string' &&
          typeof saved.body?.attraction_id === 'string' &&
          typeof saved.body?.simulation_time === 'string'
        ) {
          this.pending.set(saved);
          this.reference = saved.body.ticket_reference;
          this.attractionId = saved.body.attraction_id;
          void this.load(true);
        }
      }
    } catch {
      this.error.set('Could not restore a saved ride request. Check browser session storage.');
    }
  }
  async loadAttractions() {
    this.catalogError.set('');
    try {
      this.attractions.set(await firstValueFrom(this.catalog.attractions()));
    } catch {
      this.catalogError.set(
        'Active attractions could not be loaded. Retry before recording rides.',
      );
    }
  }
  localTime(value: string) {
    return new Date(new Date(value).getTime() + 330 * 60000).toISOString().slice(0, 16);
  }
  message(error: unknown) {
    return error instanceof HttpErrorResponse && typeof error.error?.detail === 'string'
      ? error.error.detail
      : 'Could not verify the result. Check sign-in and service connectivity, then retry.';
  }
  async load(resume = false) {
    if (this.busy() || (this.pending() && !resume)) return;
    this.busy.set(true);
    this.error.set('');
    this.notice.set('');
    this.lookup.set(null);
    try {
      const value = await firstValueFrom(this.api.lookup(this.reference.trim().toUpperCase()));
      this.lookup.set(value);
      this.simulationTime = this.localTime(value.check_in?.occurred_at ?? value.ticket.starts_at);
      if (this.pending())
        this.simulationTime = this.localTime(this.pending()!.body.simulation_time);
    } catch (error) {
      this.error.set(this.message(error));
    } finally {
      this.busy.set(false);
    }
  }
  async checkIn() {
    const value = this.lookup();
    if (!value || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      const result = await firstValueFrom(
        this.api.checkIn({
          ticket_reference: value.ticket.reference,
          simulation_time: new Date(this.simulationTime + '+05:30').toISOString(),
        }),
      );
      this.lookup.set({ ...value, check_in: result });
      this.notice.set(
        result.already_checked_in
          ? 'Guest already checked in. No duplicate entry was recorded.'
          : 'Mock guest check-in recorded.',
      );
    } catch (error) {
      this.error.set(this.message(error));
    } finally {
      this.busy.set(false);
    }
  }
  async recordRide() {
    const value = this.lookup();
    if (!value?.check_in || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      let request = this.pending();
      if (!request) {
        request = {
          body: {
            ticket_reference: value.ticket.reference,
            attraction_id: this.attractionId,
            simulation_time: new Date(this.simulationTime + '+05:30').toISOString(),
          },
          key: crypto.randomUUID(),
        };
        sessionStorage.setItem(this.retryStorageKey, JSON.stringify(request));
        this.pending.set(request);
      }
      const ride = await firstValueFrom(this.api.ride(request.body, request.key));
      const existing = value.recent_rides.some((row) => row.id === ride.id);
      this.lookup.set({
        ...value,
        check_in: { ...value.check_in, ride_count: value.check_in.ride_count + (existing ? 0 : 1) },
        recent_rides: [ride, ...value.recent_rides.filter((row) => row.id !== ride.id)].slice(
          0,
          20,
        ),
      });
      this.pending.set(null);
      sessionStorage.removeItem(this.retryStorageKey);
      this.notice.set('Mock ride usage recorded. Use a new submission only for a separate ride.');
    } catch (error) {
      this.error.set(this.message(error));
      // Validation/authorization failures cannot have committed this ride. Unknown results keep the exact retry.
      if (error instanceof HttpErrorResponse && [400, 404, 409, 422].includes(error.status)) {
        this.pending.set(null);
        sessionStorage.removeItem(this.retryStorageKey);
      }
    } finally {
      this.busy.set(false);
    }
  }
}
