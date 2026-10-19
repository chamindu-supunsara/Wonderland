SELECT tier_code, SUM(purchases) AS purchases, SUM(guest_tickets) AS guest_tickets,
       SUM(simulated_revenue_minor)/100.0 AS simulated_revenue_usd
FROM reporting.mock_daily_purchases GROUP BY tier_code ORDER BY tier_code;
