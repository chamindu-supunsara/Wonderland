# Mock business visualization — Step 08

Two connected local Metabase dashboards report mock guest arrivals, popular rides, hourly activity, package-tier arrival counts and pipeline health. The six exact queries and local dashboard/question names/IDs are in `metabase/`. Recreate them through Metabase's SQL editor using [Step 08](../docs/steps/08-mock-analytics.md).

Metabase uses a separate persistent PostgreSQL application database and reads aggregate reporting views through a restricted role. No real attendance or collected revenue is reported. AWS Admission event delivery and financial reporting remain future work.

