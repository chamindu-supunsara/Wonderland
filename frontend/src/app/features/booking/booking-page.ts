import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import {
  Booking,
  BookingApi,
  BookingDraft,
  BookingPolicy,
  VisitSlot,
} from '../../core/api/booking-api';
import { CatalogApi } from '../../core/api/catalog-api';
import { TicketTier } from '../../core/api/catalog.models';

@Component({
  selector: 'app-booking-page',
  imports: [FormsModule, RouterLink, CurrencyPipe, DatePipe],
  templateUrl: './booking-page.html',
  styleUrl: './booking.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BookingPage {
  private api = inject(BookingApi);
  private catalog = inject(CatalogApi);
  private route = inject(ActivatedRoute);
  readonly tiers = signal<TicketTier[]>([]);
  readonly slots = signal<VisitSlot[]>([]);
  readonly policy = signal<BookingPolicy | null>(null);
  readonly loading = signal(true);
  readonly slotsLoading = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly review = signal(false);
  readonly result = signal<Booking | null>(null);
  readonly uncertain = signal(false);
  tierId = '';
  visitDate = '';
  slotId = '';
  guests = 1;
  // Signals for derived selection are unnecessary: template methods read ngModel values directly.
  private slotRequest = 0;
  private attempt: { key: string; body: BookingDraft } | null = null;
  constructor() {
    void this.load();
  }
  tier() {
    return this.tiers().find((t) => t.id === this.tierId);
  }
  slot() {
    return this.slots().find((s) => s.id === this.slotId);
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const [tiers, policy] = await Promise.all([
        firstValueFrom(this.catalog.ticketTiers()),
        firstValueFrom(this.api.policy()),
      ]);
      this.tiers.set(tiers);
      this.policy.set(policy);
      this.tierId =
        tiers.find((t) => t.id === this.route.snapshot.queryParamMap.get('tier'))?.id ??
        tiers[0]?.id ??
        '';
      this.guests = this.tier()?.min_guests ?? 1;
      this.visitDate = policy.today;
      await this.loadSlots();
    } catch (e) {
      this.error.set(bookingError(e));
    } finally {
      this.loading.set(false);
    }
  }
  changeTier() {
    this.guests = this.tier()?.min_guests ?? 1;
    this.review.set(false);
  }
  async loadSlots() {
    const request = ++this.slotRequest;
    this.slotId = '';
    this.review.set(false);
    this.slots.set([]);
    this.slotsLoading.set(true);
    this.error.set('');
    if (!this.visitDate) {
      this.slotsLoading.set(false);
      return;
    }
    try {
      const rows = await firstValueFrom(this.api.slots(this.visitDate));
      if (request === this.slotRequest) this.slots.set(rows);
    } catch (e) {
      if (request === this.slotRequest) this.error.set(bookingError(e));
    } finally {
      if (request === this.slotRequest) this.slotsLoading.set(false);
    }
  }
  reviewBooking() {
    this.error.set('');
    const tier = this.tier(),
      slot = this.slot();
    if (
      !tier ||
      !slot ||
      !Number.isInteger(this.guests) ||
      this.guests < tier.min_guests ||
      this.guests > tier.max_guests ||
      this.guests > slot.remaining_guests
    ) {
      this.error.set('Choose an available slot and a whole guest count within the package limits.');
      return;
    }
    this.review.set(true);
  }
  async submit() {
    if (this.busy() || !this.review()) return;
    if (!this.attempt) {
      const tier = this.tier();
      if (!tier) return;
      this.attempt = {
        key: crypto.randomUUID(),
        body: {
          tier_id: tier.id,
          slot_id: this.slotId,
          guest_count: this.guests,
          expected_price_version: tier.price_version,
        },
      };
    }
    this.busy.set(true);
    this.error.set('');
    try {
      const result = await firstValueFrom(this.api.create(this.attempt.body, this.attempt.key));
      this.result.set(result);
      this.uncertain.set(false);
      this.attempt = null;
    } catch (e) {
      // Keep the exact body/key across unknown outcomes. Never silently create a second hold.
      this.error.set(bookingError(e));
      const definitive =
        e instanceof HttpErrorResponse && [400, 401, 403, 404, 409, 422, 503].includes(e.status);
      this.uncertain.set(!definitive);
      if (definitive) {
        this.attempt = null;
        this.review.set(false);
      }
    } finally {
      this.busy.set(false);
    }
  }
  async reloadOptions() {
    if (this.uncertain()) return;
    await this.load();
  }
}
export function bookingError(e: unknown): string {
  if (e instanceof HttpErrorResponse) {
    if (e.status === 401) return 'Your session expired. Sign out and sign in again.';
    if (e.status === 403) return 'Administrator access is required for this action.';
    if (e.status === 409)
      return typeof e.error?.detail === 'string'
        ? e.error.detail
        : 'Availability changed. Reload and review again.';
    if (e.status === 422)
      return 'Check the date, local times, whole guest count and package limits.';
    if (e.status === 404) return 'The booking or slot was not found for your account.';
    if (e.status === 503) return 'Booking or pricing is unavailable. Try again shortly.';
  }
  return 'The request could not be confirmed. Retry the same attempt or check My bookings before making another reservation.';
}
