import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { API_BASE_URL } from './api-config';
import { CatalogApi } from './catalog-api';

describe('CatalogApi', () => {
  let http: HttpTestingController;
  let api: CatalogApi;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    api = TestBed.inject(CatalogApi);
  });
  afterEach(() => http.verify());

  it('loads attractions from the Python API route', () => {
    let result: unknown;
    api.attractions().subscribe((value) => (result = value));
    const request = http.expectOne('/api/v1/attractions');
    expect(request.request.method).toBe('GET');
    request.flush([]);
    expect(result).toEqual([]);
  });

  it('supports a separately configured cloud gateway URL', () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: 'https://gateway.example/api/v1' },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    TestBed.inject(CatalogApi).ticketTiers().subscribe();
    http.expectOne('https://gateway.example/api/v1/ticket-tiers').flush([]);
  });
});
