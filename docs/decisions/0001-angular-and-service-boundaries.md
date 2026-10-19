# Decision 0001: Angular frontend and Python service boundaries

Status: accepted for this project.

Cloud account preference confirmed by the user: personal AWS account. Region, CLI profile, permissions, and deployment budget remain to be confirmed before provisioning. No AWS resources were created in Step 01.

The user selected Angular. The brief allows React or a similar framework, so Angular supplies the browser UI while FastAPI supplies Python microservices. Angular 21 was selected to match the installed Node 22.19.0 without a global runtime upgrade. AWS Amplify Hosting and Cognito remain in the cloud plan; choosing Angular does not remove those rubric items.

The five planned service boundaries are Catalog, Booking, Payment, Admission, and Analytics. Cognito owns credentials. A budget-conscious shared RDS PostgreSQL instance will use service-owned schemas/users, with no direct writes across boundaries. Shared database failure remains a documented limitation.

Milestone 01 implements Catalog reads and real persistence only. Mutating admin APIs wait for authorization. The future admin tier update must preserve pricing history and publish change events. Frontend placeholders must not be reported as working booking/payment features.

Reference checked during setup: https://angular.dev/reference/versions

