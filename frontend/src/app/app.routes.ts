import { Routes } from '@angular/router';
import { signedInGuard, administratorGuard } from './core/auth/auth-guards';

export const routes: Routes = [
  {
    path: 'admin/admission',
    canActivate: [administratorGuard],
    loadComponent: () =>
      import('./features/admission/staff-page').then((m) => m.StaffAdmissionPage),
    title: 'Mock admission · Wonderland',
  },
  {
    path: 'visits',
    canActivate: [signedInGuard],
    loadComponent: () =>
      import('./features/admission/visit-history-page').then((m) => m.VisitHistoryPage),
    title: 'My visit history · Wonderland',
  },
  {
    path: 'checkout/:id',
    canActivate: [signedInGuard],
    loadComponent: () => import('./features/booking/checkout-page').then((m) => m.CheckoutPage),
    title: 'Mock checkout · Wonderland',
  },
  {
    path: 'bookings/:id/tickets',
    canActivate: [signedInGuard],
    loadComponent: () =>
      import('./features/booking/guest-tickets-page').then((m) => m.GuestTicketsPage),
    title: 'Demonstration tickets · Wonderland',
  },
  {
    path: 'book',
    canActivate: [signedInGuard],
    loadComponent: () => import('./features/booking/booking-page').then((m) => m.BookingPage),
    title: 'Plan your visit · Wonderland',
  },
  {
    path: 'bookings',
    canActivate: [signedInGuard],
    loadComponent: () => import('./features/booking/history-page').then((m) => m.HistoryPage),
    title: 'My bookings · Wonderland',
  },
  {
    path: 'bookings/:id',
    canActivate: [signedInGuard],
    loadComponent: () => import('./features/booking/history-page').then((m) => m.HistoryPage),
    title: 'Your reservation · Wonderland',
  },
  {
    path: 'admin/slots',
    canActivate: [administratorGuard],
    loadComponent: () => import('./features/booking/slot-admin-page').then((m) => m.SlotAdminPage),
    title: 'Visit slots · Wonderland',
  },
  ...['login', 'signup', 'confirm', 'reset-password'].map((path) => ({
    path,
    loadComponent: () => import('./features/auth/auth-page').then((m) => m.AuthPage),
    data: { mode: path === 'reset-password' ? 'reset' : path },
    title: 'Your account · Wonderland',
  })),
  {
    path: 'account',
    canActivate: [signedInGuard],
    loadComponent: () => import('./features/auth/account-page').then((m) => m.AccountPage),
    title: 'My account · Wonderland',
  },
  {
    path: 'admin/access-check',
    canActivate: [administratorGuard],
    data: { admin: true },
    loadComponent: () => import('./features/auth/account-page').then((m) => m.AccountPage),
    title: 'Administrator verification · Wonderland',
  },
  {
    path: 'admin',
    canActivate: [administratorGuard],
    loadComponent: () => import('./features/admin/admin-page').then((m) => m.AdminPage),
    title: 'Administrator · Wonderland',
  },
  {
    path: '',
    loadComponent: () =>
      import('./features/attractions/attractions-page').then((m) => m.AttractionsPage),
    title: 'Explore the park · Wonderland',
  },
  {
    path: 'tickets',
    loadComponent: () => import('./features/tickets/tickets-page').then((m) => m.TicketsPage),
    title: 'Tickets & tiers · Wonderland',
  },
  {
    path: '**',
    loadComponent: () => import('./shared/not-found-page').then((m) => m.NotFoundPage),
    title: 'Page not found · Wonderland',
  },
];
