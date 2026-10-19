import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BookingPage } from './booking-page';
import { HistoryPage } from './history-page';
import { SlotAdminPage } from './slot-admin-page';

const tier = {
  id: 'tier-1',
  code: 'FAMILY',
  name: 'Family',
  min_guests: 1,
  max_guests: 4,
  amount_minor: 14000,
  currency: 'USD',
  price_version: 3,
};
const policy = {
  today: '2026-10-16',
  last_date: '2027-01-14',
  timezone: 'Asia/Colombo',
  hold_minutes: 30,
};
const slot = {
  id: 'slot-1',
  visit_date: '2026-10-17',
  starts_at: '2026-10-17T03:30:00Z',
  ends_at: '2026-10-17T06:30:00Z',
  remaining_guests: 4,
  capacity_guests: 4,
  held_guests: 0,
  confirmed_guests: 0,
  timezone: 'Asia/Colombo',
};
const booking = {
  reference: 'WL-TEST',
  ...slot,
  id: 'booking-1',
  slot_id: slot.id,
  tier_id: tier.id,
  tier_code: tier.code,
  tier_name: tier.name,
  guest_count: 4,
  amount_minor: 14000,
  currency: 'USD',
  price_version: 3,
  status: 'PENDING_PAYMENT',
  created_at: '2026-10-16T03:00:00Z',
  expires_at: '2026-10-16T03:30:00Z',
};
describe('Booking workflow', () => {
  let http: HttpTestingController;
  function configure() {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  }
  async function setup() {
    configure();
    const fixture = TestBed.createComponent(BookingPage);
    http.expectOne('/api/v1/ticket-tiers').flush([tier]);
    http.expectOne('/api/v1/booking-policy').flush(policy);
    await Promise.resolve();
    await Promise.resolve();
    http.expectOne('/api/v1/visit-slots?date=2026-10-16').flush([slot]);
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }
  afterEach(() => {
    try {
      http?.verify();
    } finally {
      TestBed.resetTestingModule();
    }
  });
  it('reviews before sending a server-priced idempotent reservation', async () => {
    const fixture = await setup();
    const page = fixture.componentInstance;
    page.guests = 4;
    page.slotId = slot.id;
    page.reviewBooking();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Ready to reserve?');
    http.expectNone('/api/v1/bookings');
    const saving = page.submit();
    const req = http.expectOne('/api/v1/bookings');
    expect(req.request.headers.get('Idempotency-Key')).toBeTruthy();
    expect(req.request.body).toEqual({
      tier_id: tier.id,
      slot_id: slot.id,
      guest_count: 4,
      expected_price_version: 3,
    });
    req.flush(booking);
    await saving;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Pending payment');
    expect(fixture.nativeElement.textContent).toContain('WL-TEST');
  });
  it('blocks invalid guest counts before a reservation', async () => {
    const fixture = await setup(),
      page = fixture.componentInstance;
    page.slotId = slot.id;
    for (const guests of [0, 5, 1.5]) {
      page.guests = guests;
      page.reviewBooking();
      expect(page.review()).toBe(false);
    }
    http.expectNone('/api/v1/bookings');
  });
  it('shows an expired retry result without claiming an active hold', async () => {
    const fixture = await setup(),
      page = fixture.componentInstance;
    page.guests = 4;
    page.slotId = slot.id;
    page.reviewBooking();
    const saving = page.submit();
    http.expectOne('/api/v1/bookings').flush({ ...booking, status: 'EXPIRED' });
    await saving;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Expired');
    expect(fixture.nativeElement.textContent).not.toContain('Your hold ends');
  });
  it('retries unknown outcomes with the identical body and key', async () => {
    const fixture = await setup(),
      page = fixture.componentInstance;
    page.guests = 4;
    page.slotId = slot.id;
    page.reviewBooking();
    const first = page.submit(),
      req = http.expectOne('/api/v1/bookings');
    const key = req.request.headers.get('Idempotency-Key'),
      body = req.request.body;
    req.flush('gateway failure', { status: 502, statusText: 'Bad gateway' });
    await first;
    expect(page.uncertain()).toBe(true);
    const retry = page.submit(),
      second = http.expectOne('/api/v1/bookings');
    expect(second.request.headers.get('Idempotency-Key')).toBe(key);
    expect(second.request.body).toEqual(body);
    second.flush(booking);
    await retry;
  });
  it('shows capacity conflicts without claiming a successful reservation', async () => {
    const fixture = await setup(),
      page = fixture.componentInstance;
    page.guests = 4;
    page.slotId = slot.id;
    page.reviewBooking();
    const saving = page.submit();
    http
      .expectOne('/api/v1/bookings')
      .flush({ detail: 'This slot is full.' }, { status: 409, statusText: 'Conflict' });
    await saving;
    expect(page.result()).toBeNull();
    expect(page.review()).toBe(false);
    expect(page.error()).toContain('full');
  });
  it('ignores availability responses for an earlier date', async () => {
    const fixture = await setup(),
      page = fixture.componentInstance;
    page.visitDate = '2026-10-17';
    const first = page.loadSlots(),
      old = http.expectOne('/api/v1/visit-slots?date=2026-10-17');
    page.visitDate = '2026-10-18';
    const second = page.loadSlots();
    http.expectOne('/api/v1/visit-slots?date=2026-10-18').flush([]);
    await second;
    old.flush([slot]);
    await first;
    expect(page.slots()).toEqual([]);
  });
  it('requires explicit cancellation confirmation and refreshes owner history', async () => {
    configure();
    const fixture = TestBed.createComponent(HistoryPage);
    http.expectOne('/api/v1/bookings/me?limit=20&offset=0').flush([booking]);
    await fixture.whenStable();
    fixture.detectChanges();
    let buttons = Array.from(
      fixture.nativeElement.querySelectorAll('button'),
    ) as HTMLButtonElement[];
    buttons.find((b) => b.textContent?.includes('Cancel unpaid'))!.click();
    fixture.detectChanges();
    http.expectNone('/api/v1/bookings/booking-1/cancel');
    buttons = Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[];
    buttons.find((b) => b.textContent?.includes('Confirm cancellation'))!.click();
    http.expectOne('/api/v1/bookings/booking-1/cancel').flush({ ...booking, status: 'CANCELLED' });
    await Promise.resolve();
    http
      .expectOne('/api/v1/bookings/me?limit=20&offset=0')
      .flush([{ ...booking, status: 'CANCELLED' }]);
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Cancelled');
  });
  it('posts administrator slots with explicit local times and capacity', async () => {
    configure();
    const fixture = TestBed.createComponent(SlotAdminPage);
    http.expectOne('/api/v1/booking-policy').flush(policy);
    await Promise.resolve();
    http.expectOne('/api/v1/visit-slots?date=2026-10-16').flush([]);
    await fixture.whenStable();
    const page = fixture.componentInstance;
    page.date = '2026-10-17';
    page.capacity = 4;
    const saving = page.save(),
      request = http.expectOne('/api/v1/admin/visit-slots');
    expect(request.request.body).toEqual({
      visit_date: '2026-10-17',
      start_time: '09:00',
      end_time: '12:00',
      capacity_guests: 4,
    });
    request.flush(slot);
    await Promise.resolve();
    http.expectOne('/api/v1/visit-slots?date=2026-10-17').flush([slot]);
    await saving;
    expect(page.notice()).toContain('added');
  });
});
