SELECT 'Guest arrivals' AS metric,total_guest_arrivals::text AS value FROM reporting.mock_pipeline_health
UNION ALL SELECT 'Ride uses',total_ride_uses::text FROM reporting.mock_pipeline_health
UNION ALL SELECT 'Rides awaiting arrival event',rides_awaiting_arrival::text FROM reporting.mock_pipeline_health
UNION ALL SELECT 'Historical maximum delivery lag (seconds)',ROUND(max_delivery_lag_seconds,2)::text FROM reporting.mock_pipeline_health;

