# Wonderland Angular frontend

Angular 21 standalone components with lazy routes, signals, typed HttpClient calls, SCSS, and Vitest tests.

Read the root README and docs/steps/01-foundation.md before starting. From this directory:

```powershell
npx.cmd --yes npm@11.6.2 ci
npm.cmd start
npm.cmd test
npm.cmd run build
```

The development server runs at http://127.0.0.1:4200 and proxies /api/** to the Catalog API at http://127.0.0.1:8001. The proxy is configured by npm start; running ng serve directly omits it. Start the API/database first using the root instructions.

Pages currently implemented: attraction browsing/filtering and ticket-tier pricing. Data comes from FastAPI/PostgreSQL. Authentication, booking, history, staff/admin tools, and cloud configuration remain on the roadmap.

Production browser output: dist/wonderland/browser. A later Amplify Hosting milestone will configure its build, SPA rewrites, Cognito, and API Gateway URL.

Generate future components with npm.cmd exec ng generate component features/<feature>/<name>. Use features for business pages, core for API/auth/configuration, and shared for reusable presentation components. Add meaningful tests when changing behavior.
