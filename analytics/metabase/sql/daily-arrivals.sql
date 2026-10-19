SELECT visit_date, SUM(guest_arrivals) AS guest_arrivals
FROM reporting.mock_daily_arrivals
GROUP BY visit_date ORDER BY visit_date;

