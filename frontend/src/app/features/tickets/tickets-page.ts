import { PRIME_FORM_UI } from '../../shared/prime-ui';
import { CurrencyPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CatalogApi } from '../../core/api/catalog-api';
import { TicketTier } from '../../core/api/catalog.models';
import { TagModule } from 'primeng/tag';

@Component({
  selector: 'app-tickets-page',
  imports: [...PRIME_FORM_UI, CurrencyPipe, RouterLink, TagModule],
  templateUrl: './tickets-page.html',
  styleUrl: './tickets-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TicketsPage {
  private readonly api = inject(CatalogApi);
  private readonly destroyRef = inject(DestroyRef);
  readonly tiers = signal<TicketTier[]>([]);
  readonly loading = signal(false);
  readonly error = signal(false);

  constructor() {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.error.set(false);
    this.api
      .ticketTiers()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (tiers) => {
          this.tiers.set(tiers);
          this.loading.set(false);
        },
        error: () => {
          this.error.set(true);
          this.loading.set(false);
        },
      });
  }
}
