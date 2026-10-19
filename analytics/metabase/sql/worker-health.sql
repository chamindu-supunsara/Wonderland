SELECT 'Last poll (Asia/Colombo)' AS metric, to_char(worker_last_polled_at AT TIME ZONE 'Asia/Colombo','YYYY-MM-DD HH24:MI:SS') AS value FROM reporting.mock_worker_health
UNION ALL SELECT 'Heartbeat age (seconds)',ROUND(heartbeat_age_seconds,1)::text FROM reporting.mock_worker_health
UNION ALL SELECT 'Pending events',pending_events::text FROM reporting.mock_worker_health
UNION ALL SELECT 'Retained errors (last batch)',retained_errors::text FROM reporting.mock_worker_health;
