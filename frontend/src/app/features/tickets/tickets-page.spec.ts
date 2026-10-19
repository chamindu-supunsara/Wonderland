import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { TicketsPage } from './tickets-page';

describe('TicketsPage', () => {
  it('formats server prices in cents as package prices', () => {
    TestBed.configureTestingModule({
      imports: [TicketsPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    const http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(TicketsPage);
    http
      .expectOne('/api/v1/ticket-tiers')
      .flush([
        {
          id: '1',
          code: 'FAMILY',
          name: 'Family',
          min_guests: 1,
          max_guests: 4,
          amount_minor: 14000,
          currency: 'USD',
          price_version: 1,
        },
      ]);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.price').textContent).toContain('$140');
    expect(fixture.nativeElement.querySelector('.tier-card').textContent).toContain(
      'Up to 4 guests',
    );
    expect(fixture.nativeElement.textContent).toContain('Prices are per package');
    http.verify();
  });
});
