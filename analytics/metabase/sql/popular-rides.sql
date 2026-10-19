SELECT (array_agg(attraction_name ORDER BY visit_date DESC))[1] AS attraction_name,
 SUM(ride_uses) AS ride_uses
FROM reporting.mock_popular_rides GROUP BY attraction_key
ORDER BY ride_uses DESC,attraction_name;

