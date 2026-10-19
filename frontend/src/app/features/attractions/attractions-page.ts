import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { CatalogApi } from '../../core/api/catalog-api';
import { Attraction } from '../../core/api/catalog.models';

@Component({
  selector: 'app-attractions-page',
  imports: [RouterLink],
  templateUrl: './attractions-page.html',
  styleUrl: './attractions-page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AttractionsPage {
  private readonly api = inject(CatalogApi);
  private readonly destroyRef = inject(DestroyRef);
  readonly attractions = signal<Attraction[]>([]);
  readonly loading = signal(false);
  readonly error = signal(false);
  readonly selectedCategory = signal('ALL');
  readonly categories = [
    { value: 'ALL', label: 'All experiences' },
    { value: 'ROLLER_COASTER', label: 'Big thrills' },
    { value: 'KIDS', label: 'Little adventurers' },
    { value: 'WATER', label: 'Make a splash' },
    { value: 'INTERACTIVE', label: 'Play & discover' },
  ];
  readonly filteredAttractions = computed(() =>
    this.attractions().filter(
      (ride) => this.selectedCategory() === 'ALL' || ride.category === this.selectedCategory(),
    ),
  );

  constructor() {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.error.set(false);
    this.api
      .attractions()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (rides) => {
          this.attractions.set(rides);
          this.loading.set(false);
        },
        error: () => {
          this.error.set(true);
          this.loading.set(false);
        },
      });
  }

  categoryLabel(value: string) {
    return this.categories.find((category) => category.value === value)?.label ?? value;
  }
}
