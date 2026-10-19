import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { CheckoutPage } from './checkout-page';

const checkout = { id: 'checkout-1', booking_id: 'booking-1', booking_reference: 'WL-TEST', amount_minor: 14000, currency: 'USD', status: 'READY', outcome: null, mode: 'MOCK' };
describe('Mock checkout', () => {
  let http: HttpTestingController;
  function setup(row = checkout) {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([]), { provide: ActivatedRoute, useValue: { snapshot: { paramMap: new Map([['id', 'booking-1']]) } } }] });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(CheckoutPage);
    const request = http.expectOne('/api/v1/payments/checkouts');
    expect(request.request.body).toEqual({ booking_id: 'booking-1' });
    request.flush(row);
    fixture.detectChanges();
    return fixture;
  }
  afterEach(() => { http.verify(); TestBed.resetTestingModule(); });
  it('labels simulation and links confirmed demonstration tickets', () => {
    const fixture = setup();
    expect(fixture.nativeElement.textContent).toContain('No real charge');
    fixture.componentInstance.complete('success');
    const request = http.expectOne('/api/v1/payments/checkouts/checkout-1/complete');
    expect(request.request.body).toEqual({ outcome: 'success' });
    request.flush({ ...checkout, outcome: 'success', status: 'SUCCEEDED' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('a[href="/bookings/booking-1/tickets"]')).toBeTruthy();
    expect(fixture.nativeElement.textContent).not.toContain('Simulate failure');
  });
  it('preserves decision after unknown response and retries the same checkout', () => {
    const fixture = setup();
    fixture.componentInstance.complete('success');
    http.expectOne('/api/v1/payments/checkouts/checkout-1/complete').flush({}, { status: 503, statusText: 'Unavailable' });
    fixture.componentInstance.complete('failure');
    http.expectNone('/api/v1/payments/checkouts/checkout-1/complete');
    fixture.componentInstance.complete('success');
    const retry = http.expectOne('/api/v1/payments/checkouts/checkout-1/complete');
    expect(retry.request.body).toEqual({ outcome: 'success' });
    retry.flush({ ...checkout, outcome: 'success', status: 'SUCCEEDED' });
  });
  it('shows released capacity after failed simulation', () => {
    const fixture = setup();
    fixture.componentInstance.complete('failure');
    http.expectOne('/api/v1/payments/checkouts/checkout-1/complete').flush({ ...checkout, outcome: 'failure', status: 'FAILED' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('guest places have been released');
    expect(fixture.nativeElement.querySelector('a[href$="/tickets"]')).toBeFalsy();
  });
});
