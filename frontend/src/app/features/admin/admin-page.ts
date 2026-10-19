import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import {
  AdminApi,
  AdminAttraction,
  AdminTier,
  AttractionDraft,
  AuditEvent,
  parsePrice,
  PriceVersion,
} from '../../core/api/admin-api';

@Component({
  selector: 'app-admin-page',
  imports: [FormsModule, RouterLink, CurrencyPipe, DatePipe],
  templateUrl: './admin-page.html',
  styleUrl: './admin-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminPage {
  readonly localAnalytics = ['127.0.0.1', 'localhost'].includes(window.location.hostname);
  private readonly api = inject(AdminApi);
  readonly section = signal<'attractions' | 'pricing' | 'activity'>('attractions');
  readonly attractions = signal<AdminAttraction[]>([]);
  readonly tiers = signal<AdminTier[]>([]);
  readonly events = signal<AuditEvent[]>([]);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly editor = signal<AdminAttraction | 'new' | null>(null);
  readonly retirement = signal<AdminAttraction | null>(null);
  readonly selectedTier = signal<AdminTier | null>(null);
  readonly prices = signal<PriceVersion[]>([]);
  readonly historyLoading = signal(false);
  readonly historyError = signal('');
  readonly priceConfirmation = signal<number | null>(null);
  readonly statusFilter = signal('ALL');
  readonly search = signal('');
  readonly filtered = computed(() =>
    this.attractions().filter(
      (ride) =>
        (this.statusFilter() === 'ALL' || ride.status === this.statusFilter()) &&
        `${ride.name} ${ride.description}`.toLowerCase().includes(this.search().toLowerCase()),
    ),
  );
  readonly activeCount = computed(
    () => this.attractions().filter((a) => a.status === 'ACTIVE').length,
  );
  readonly categories = [
    { code: 'ROLLER_COASTER', label: 'Roller coaster' },
    { code: 'KIDS', label: 'Kids' },
    { code: 'WATER', label: 'Water' },
    { code: 'INTERACTIVE', label: 'Interactive' },
  ];
  draft: AttractionDraft = this.emptyDraft();
  priceInput = '';
  private historyRequest = 0;

  constructor() {
    void this.load();
  }
  emptyDraft(): AttractionDraft {
    return {
      name: '',
      description: '',
      category: 'ROLLER_COASTER',
      thrill_level: 'LOW',
      min_age: null,
      min_height_cm: null,
      guidance_text: '',
    };
  }
  categoryLabel(code: string) {
    return this.categories.find((c) => c.code === code)?.label ?? code;
  }
  editingName() {
    const ride = this.editor();
    return ride && ride !== 'new' ? ride.name : 'New attraction';
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const [attractions, tiers, events] = await Promise.all([
        firstValueFrom(this.api.attractions()),
        firstValueFrom(this.api.tiers()),
        firstValueFrom(this.api.audit()),
      ]);
      this.attractions.set(attractions);
      this.tiers.set(tiers);
      this.events.set(events);
    } catch (error) {
      this.error.set(this.describeError(error));
    } finally {
      this.loading.set(false);
    }
  }
  begin(ride: AdminAttraction | 'new') {
    if (this.saving() || this.loading()) return;
    this.error.set('');
    this.notice.set('');
    this.retirement.set(null);
    this.draft =
      ride === 'new'
        ? this.emptyDraft()
        : {
            name: ride.name,
            description: ride.description,
            category: ride.category,
            thrill_level: ride.thrill_level,
            min_age: ride.min_age,
            min_height_cm: ride.min_height_cm,
            guidance_text: ride.guidance_text,
          };
    this.editor.set(ride);
  }
  async saveAttraction() {
    const ride = this.editor();
    if (!ride || this.saving()) return;
    if (
      ![this.draft.name, this.draft.description, this.draft.guidance_text].every((value) =>
        value.trim(),
      )
    ) {
      this.error.set('Name, description and visitor guidance cannot be blank.');
      return;
    }
    if (
      [this.draft.min_age, this.draft.min_height_cm].some(
        (value) => value !== null && !Number.isInteger(value),
      )
    ) {
      this.error.set('Minimum age and height must be whole numbers or left blank.');
      return;
    }
    this.saving.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      const result = await firstValueFrom(
        ride === 'new' ? this.api.create(this.draft) : this.api.update(ride, this.draft),
      );
      this.editor.set(null);
      this.notice.set(`${result.name} ${ride === 'new' ? 'added to the park' : 'updated'}.`);
      await this.load();
    } catch (error) {
      this.error.set(this.describeError(error));
    } finally {
      this.saving.set(false);
    }
  }
  async retire() {
    const ride = this.retirement();
    if (!ride || this.saving()) return;
    this.saving.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      await firstValueFrom(this.api.retire(ride));
      this.retirement.set(null);
      this.notice.set(`${ride.name} retired. Its record is preserved.`);
      await this.load();
    } catch (error) {
      this.error.set(this.describeError(error));
    } finally {
      this.saving.set(false);
    }
  }
  async selectTier(tier: AdminTier) {
    this.selectedTier.set(tier);
    this.priceInput = (tier.amount_minor / 100).toFixed(2);
    this.priceConfirmation.set(null);
    this.error.set('');
    this.notice.set('');
    await this.loadHistory(tier.id);
  }
  async loadHistory(id: string) {
    const request = ++this.historyRequest;
    this.historyLoading.set(true);
    this.historyError.set('');
    this.prices.set([]);
    try {
      const prices = await firstValueFrom(this.api.history(id));
      if (request === this.historyRequest) this.prices.set(prices);
    } catch {
      if (request === this.historyRequest)
        this.historyError.set('Price history could not be loaded. Select the tier again to retry.');
    } finally {
      if (request === this.historyRequest) this.historyLoading.set(false);
    }
  }
  reviewPrice() {
    const amount = parsePrice(this.priceInput);
    this.error.set('');
    if (amount === null) {
      this.error.set(
        'Enter a USD price from 0.01 to 1,000,000.00, with at most two decimal places.',
      );
      return;
    }
    if (amount === this.selectedTier()?.amount_minor) {
      this.error.set('Enter a different price to create a new version.');
      return;
    }
    this.priceConfirmation.set(amount);
  }
  async publish() {
    const tier = this.selectedTier();
    const amount = this.priceConfirmation();
    if (!tier || amount === null || this.saving()) return;
    this.saving.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      await firstValueFrom(this.api.publish(tier, amount));
      this.priceConfirmation.set(null);
      this.selectedTier.set(null);
      this.notice.set(`${tier.name} price published. Earlier versions are preserved.`);
      await this.load();
      const updated = this.tiers().find((item) => item.id === tier.id);
      if (updated) {
        this.selectedTier.set(updated);
        this.priceInput = (updated.amount_minor / 100).toFixed(2);
        await this.loadHistory(updated.id);
      }
    } catch (error) {
      this.error.set(this.describeError(error));
    } finally {
      this.saving.set(false);
    }
  }
  reloadLatest() {
    this.editor.set(null);
    this.retirement.set(null);
    this.selectedTier.set(null);
    this.priceConfirmation.set(null);
    this.notice.set('');
    void this.load();
  }
  describeError(error: unknown) {
    if (error instanceof HttpErrorResponse) {
      if (error.status === 401) return 'Your session expired. Sign out and sign in again.';
      if (error.status === 403)
        return 'Administrator access is required. Check your account permissions.';
      if (error.status === 409)
        return 'This record changed or cannot accept that update. Reload latest data, review it and try again.';
      if (error.status === 422)
        return 'Check the form values. Text limits, category, whole-number suitability and a positive price are required.';
      if (error.status === 404) return 'This record was not found. Reload the latest data.';
    }
    return 'The request could not be confirmed. Reload latest data before retrying a save, to check whether it succeeded.';
  }
}
