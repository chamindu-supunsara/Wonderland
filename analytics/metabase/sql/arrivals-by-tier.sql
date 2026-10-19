SELECT tier_code, SUM(guest_arrivals) AS guest_arrivals
FROM reporting.mock_daily_arrivals GROUP BY tier_code ORDER BY guest_arrivals DESC,tier_code;

