SELECT LPAD(hour_of_day::text,2,'0') || ':00' AS local_hour,
 SUM(guest_arrivals) AS guest_arrivals, SUM(ride_uses) AS ride_uses
FROM reporting.mock_daily_hour_grid GROUP BY hour_of_day ORDER BY hour_of_day;

