import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { API_BASE_URL } from '../../core/api/api-config';
import { AdminAttraction, AdminTier, parsePrice } from '../../core/api/admin-api';
import { AdminPage } from './admin-page';

const draft = {
  name: 'Test Ride',
  description: 'A gentle ride',
  category: 'KIDS',
  thrill_level: 'LOW',
  min_age: null,
  min_height_cm: 90,
  guidance_text: 'Follow staff instructions.',
};
const ride: AdminAttraction = {
  ...draft,
  id: 'ride-1',
  status: 'ACTIVE',
  revision: 3,
  created_at: '2026-10-15T00:00:00Z',
  updated_at: '2026-10-15T00:00:00Z',
};
const tier: AdminTier = {
  id: 'tier-1',
  code: 'INDIVIDUAL',
  name: 'Individual',
  min_guests: 1,
  max_guests: 1,
  amount_minor: 4000,
  currency: 'USD',
  price_version: 1,
  active: true,
};

describe('Administrator catalog forms', () => {
  let http: HttpTestingController;
  function flushLists() {
    http.expectOne('/api/v1/admin/attractions').flush([ride]);
    http.expectOne('/api/v1/admin/ticket-tiers').flush([tier]);
    http.expectOne('/api/v1/admin/audit').flush([]);
  }
  async function setup() {
    TestBed.configureTestingModule({
      imports: [AdminPage],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: '/api/v1' },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(AdminPage);
    flushLists();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }
  afterEach(() => http?.verify());

  it('creates with only editable fields and refreshes the persisted catalog', async () => {
    const fixture = await setup();
    const page = fixture.componentInstance;
    page.begin('new');
    page.draft = { ...draft };
    const saving = page.saveAttraction();
    const request = http.expectOne('/api/v1/admin/attractions');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(draft);
    request.flush({ ...ride, revision: 1 });
    await Promise.resolve();
    flushLists();
    await saving;
    fixture.detectChanges();
    expect(page.editor()).toBeNull();
    expect(fixture.nativeElement.querySelector('[role="status"]').textContent).toContain(
      'added to the park',
    );
  });
  it('sends the revision and keeps edits visible on a stale update conflict', async () => {
    const fixture = await setup();
    const page = fixture.componentInstance;
    page.begin(ride);
    page.draft.name = 'New name';
    const saving = page.saveAttraction();
    const request = http.expectOne('/api/v1/admin/attractions/ride-1');
    expect(request.request.body.expected_revision).toBe(3);
    expect(request.request.body.status).toBeUndefined();
    request.flush({ detail: 'changed' }, { status: 409, statusText: 'Conflict' });
    await saving;
    expect(page.editor()).toEqual(ride);
    expect(page.draft.name).toBe('New name');
    expect(page.error()).toContain('Reload latest');
  });
  it('rejects blank text and fractional suitability before a write', async () => {
    const page = (await setup()).componentInstance;
    page.begin('new');
    page.draft = { ...draft, name: ' ' };
    await page.saveAttraction();
    expect(page.error()).toContain('blank');
    page.draft = { ...draft, min_age: 1.5 };
    await page.saveAttraction();
    expect(page.error()).toContain('whole numbers');
    http.expectNone('/api/v1/admin/attractions');
  });
  it('shows a retirement confirmation before sending any retirement request', async () => {
    const fixture = await setup();
    const page = fixture.componentInstance;
    const button: HTMLButtonElement = fixture.nativeElement.querySelector(
      '[aria-label="Retire Test Ride"]',
    );
    button.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Retire Test Ride?');
    http.expectNone('/api/v1/admin/attractions/ride-1/retire');
    const saving = page.retire();
    const request = http.expectOne('/api/v1/admin/attractions/ride-1/retire');
    expect(request.request.body).toEqual({ expected_revision: 3 });
    request.flush({ ...ride, status: 'RETIRED', revision: 4 });
    await Promise.resolve();
    flushLists();
    await saving;
    expect(page.retirement()).toBeNull();
  });
  it('requires price review and publishes integer cents with the expected version', async () => {
    const page = (await setup()).componentInstance;
    const selected = page.selectTier(tier);
    http.expectOne('/api/v1/admin/ticket-tiers/tier-1/prices').flush([]);
    await selected;
    page.priceInput = '42.50';
    page.reviewPrice();
    expect(page.priceConfirmation()).toBe(4250);
    http.expectNone('/api/v1/admin/ticket-tiers/tier-1/prices');
    const saving = page.publish();
    const request = http.expectOne('/api/v1/admin/ticket-tiers/tier-1/prices');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ amount_minor: 4250, expected_version: 1 });
    request.flush({ detail: 'stale' }, { status: 409, statusText: 'Conflict' });
    await saving;
    expect(page.error()).toContain('Reload latest');
    expect(page.selectedTier()).toEqual(tier);
  });
  it('does not replace a newly selected tier history with a late earlier response', async () => {
    const page = (await setup()).componentInstance;
    const first = page.selectTier(tier);
    const old = http.expectOne('/api/v1/admin/ticket-tiers/tier-1/prices');
    const second = page.selectTier({ ...tier, id: 'tier-2', name: 'Couple' });
    http.expectOne('/api/v1/admin/ticket-tiers/tier-2/prices').flush([]);
    await second;
    old.flush([{ id: 'old', amount_minor: 4000 }]);
    await first;
    expect(page.prices()).toEqual([]);
    expect(page.selectedTier()?.id).toBe('tier-2');
  });
});

describe('USD input parsing', () => {
  it('converts decimal text to exact integer cents', () => {
    expect(parsePrice('42.50')).toBe(4250);
    expect(parsePrice('0.01')).toBe(1);
    expect(parsePrice(' 19.9 ')).toBe(1990);
    expect(parsePrice('1000000')).toBe(100000000);
  });
  it('rejects zero, negative, excessive, exponent and fractional-cent inputs', () => {
    for (const value of ['0', '-1', '1.005', '1e3', 'NaN', '1,000.00', '1000000.01', ''])
      expect(parsePrice(value)).toBeNull();
  });
});
