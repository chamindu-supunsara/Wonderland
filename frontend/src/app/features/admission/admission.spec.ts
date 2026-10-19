import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AuthService } from '../../core/auth/auth-service';
import { StaffAdmissionPage } from './staff-page';
import { VisitHistoryPage } from './visit-history-page';

const reference = 'MOCK-' + 'A'.repeat(32);
const ticket = {
  id: 'ticket-1',
  reference,
  booking_id: 'booking-1',
  booking_reference: 'WL-DEMO',
  guest_number: 1,
  tier_code: 'FAMILY',
  tier_name: 'Family',
  starts_at: '2026-10-16T03:30:00Z',
  ends_at: '2026-10-16T06:30:00Z',
};
const visit = {
  id: 'visit-1',
  ticket,
  mode: 'MOCK',
  occurred_at: ticket.starts_at,
  recorded_at: '2026-10-15T18:00:00Z',
  ride_count: 0,
};
const lookup = { ticket, check_in: null, recent_rides: [], mode: 'MOCK' };
const ride = {
  id: 'ride-1',
  attraction_id: 'attraction-1',
  attraction_name: 'River Ride',
  category: 'Family',
  occurred_at: ticket.starts_at,
  recorded_at: visit.recorded_at,
  mode: 'MOCK',
};
const storageKey = 'wonderland-mock-ride:staff-test';
describe('Mock Admission workflow', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    sessionStorage.removeItem(storageKey);
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: AuthService, useValue: { user: () => ({ userId: 'staff-test' }) } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.verify();
    sessionStorage.removeItem(storageKey);
    TestBed.resetTestingModule();
  });
  function staff() {
    const fixture = TestBed.createComponent(StaffAdmissionPage);
    http
      .expectOne('/api/v1/attractions')
      .flush([{ id: 'attraction-1', name: 'River Ride', category: 'Family' }]);
    return fixture;
  }
  async function load(page: StaffAdmissionPage, checkedIn = false) {
    page.reference = reference;
    const loading = page.load();
    http
      .expectOne('/api/v1/admissions/staff/tickets/' + reference)
      .flush({ ...lookup, check_in: checkedIn ? visit : null });
    await loading;
  }
  it('labels simulation and converts the chosen Colombo time to UTC', async () => {
    const fixture = staff();
    await load(fixture.componentInstance);
    expect(fixture.componentInstance.simulationTime).toBe('2026-10-16T09:00');
    const checking = fixture.componentInstance.checkIn();
    const request = http.expectOne('/api/v1/admissions/staff/check-ins');
    expect(request.request.body).toEqual({
      ticket_reference: reference,
      simulation_time: '2026-10-16T03:30:00.000Z',
    });
    request.flush({ ...visit, already_checked_in: false });
    await checking;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Mock guest check-in recorded');
    expect(fixture.nativeElement.textContent).toContain('No real park admission');
  });
  it('shows duplicate entry without creating another guest in the UI', async () => {
    const fixture = staff();
    await load(fixture.componentInstance, true);
    const checking = fixture.componentInstance.checkIn();
    http
      .expectOne('/api/v1/admissions/staff/check-ins')
      .flush({ ...visit, already_checked_in: true });
    await checking;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No duplicate entry was recorded');
  });
  it('requires guest check-in before any ride request', async () => {
    const fixture = staff();
    await load(fixture.componentInstance);
    await fixture.componentInstance.recordRide();
    http.expectNone('/api/v1/admissions/staff/ride-uses');
  });
  it('persists the exact ride retry across a page reload after an unknown response', async () => {
    const fixture = staff();
    await load(fixture.componentInstance, true);
    fixture.componentInstance.attractionId = 'attraction-1';
    const saving = fixture.componentInstance.recordRide();
    const request = http.expectOne('/api/v1/admissions/staff/ride-uses');
    const key = request.request.headers.get('Idempotency-Key');
    const body = request.request.body;
    request.flush({}, { status: 503, statusText: 'Unavailable' });
    await saving;
    expect(sessionStorage.getItem(storageKey)).toContain(key!);
    fixture.destroy();
    const restored = staff();
    http
      .expectOne('/api/v1/admissions/staff/tickets/' + reference)
      .flush({ ...lookup, check_in: visit });
    await restored.whenStable();
    const retrying = restored.componentInstance.recordRide();
    const retry = http.expectOne('/api/v1/admissions/staff/ride-uses');
    expect(retry.request.headers.get('Idempotency-Key')).toBe(key);
    expect(retry.request.body).toEqual(body);
    retry.flush(ride);
    await retrying;
    expect(sessionStorage.getItem(storageKey)).toBeNull();
    expect(restored.componentInstance.lookup()?.check_in?.ride_count).toBe(1);
  });
  it('allows correcting a rejected simulation time', async () => {
    const fixture = staff();
    await load(fixture.componentInstance, true);
    fixture.componentInstance.attractionId = 'attraction-1';
    const saving = fixture.componentInstance.recordRide();
    http
      .expectOne('/api/v1/admissions/staff/ride-uses')
      .flush(
        { detail: 'Ride usage cannot precede guest check-in.' },
        { status: 422, statusText: 'Invalid' },
      );
    await saving;
    expect(fixture.componentInstance.pending()).toBeNull();
    expect(fixture.componentInstance.error()).toContain('cannot precede');
  });
  it('displays own guest visits and paginated ride history', async () => {
    const fixture = TestBed.createComponent(VisitHistoryPage);
    http.expectOne('/api/v1/admissions/visits/me?limit=20&offset=0').flush([visit]);
    await fixture.whenStable();
    const loading = fixture.componentInstance.showRides(visit.id);
    http.expectOne('/api/v1/admissions/visits/visit-1/rides?limit=20&offset=0').flush([ride]);
    await loading;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('River Ride');
    expect(fixture.nativeElement.textContent).toContain('MOCK history only');
  });
  it('shows a useful history error and supports retry', async () => {
    const fixture = TestBed.createComponent(VisitHistoryPage);
    http
      .expectOne('/api/v1/admissions/visits/me?limit=20&offset=0')
      .flush({}, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    expect(fixture.componentInstance.error()).toContain('Could not load your visits');
    const retrying = fixture.componentInstance.load();
    http.expectOne('/api/v1/admissions/visits/me?limit=20&offset=0').flush([]);
    await retrying;
    expect(fixture.componentInstance.error()).toBe('');
  });
});
