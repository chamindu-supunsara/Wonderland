SELECT purchase_date, SUM(purchases) AS purchases,
       SUM(simulated_revenue_minor)/100.0 AS simulated_revenue_usd
FROM reporting.mock_daily_purchases GROUP BY purchase_date ORDER BY purchase_date;
