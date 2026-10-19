import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AttractionsPage } from './attractions-page';

const rides = [
  {
    id: '1',
    name: 'Test Coaster',
    description: 'Fast ride',
    category: 'ROLLER_COASTER',
    thrill_level: 'HIGH',
    min_age: 12,
    min_height_cm: 140,
    guidance_text: 'Follow staff instructions',
  },
  {
    id: '2',
    name: 'Test Rapids',
    description: 'Water ride',
    category: 'WATER',
    thrill_level: 'MEDIUM',
    min_age: 6,
    min_height_cm: 110,
    guidance_text: 'Expect splashes',
  },
];

describe('AttractionsPage', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [AttractionsPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('renders API results and filters the visible experiences', () => {
    const fixture = TestBed.createComponent(AttractionsPage);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Finding your next adventure');
    http.expectOne('/api/v1/attractions').flush(rides);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.ride-card').length).toBe(2);
    const waterButton = Array.from(
      fixture.nativeElement.querySelectorAll('.filters button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('Make a splash'))!;
    waterButton.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.ride-card').length).toBe(1);
    expect(fixture.nativeElement.querySelector('.ride-card').textContent).toContain('Test Rapids');
  });

  it('shows an error and recovers when the visitor retries', () => {
    const fixture = TestBed.createComponent(AttractionsPage);
    http.expectOne('/api/v1/attractions').flush({}, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
    fixture.nativeElement.querySelector('[role="alert"] button').click();
    http.expectOne('/api/v1/attractions').flush(rides);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]')).toBeNull();
    expect(fixture.nativeElement.querySelectorAll('.ride-card').length).toBe(2);
  });
});
