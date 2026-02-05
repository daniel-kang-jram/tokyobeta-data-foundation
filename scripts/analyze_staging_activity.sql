-- Analyze staging tables for recent activity (within 1 year)
-- Generated on 2026-02-05

SET @cutoff_date = DATE_SUB(CURDATE(), INTERVAL 1 YEAR);

SELECT 
    CONCAT('Analyzing staging tables for activity since: ', @cutoff_date) as 'Analysis Details';

-- Get all staging tables with their date columns
SELECT 
    t.TABLE_NAME,
    GROUP_CONCAT(c.COLUMN_NAME ORDER BY c.ORDINAL_POSITION) as date_columns,
    t.TABLE_ROWS as approx_total_rows
FROM information_schema.TABLES t
LEFT JOIN information_schema.COLUMNS c 
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA 
    AND t.TABLE_NAME = c.TABLE_NAME
    AND c.DATA_TYPE IN ('date', 'datetime', 'timestamp')
WHERE t.TABLE_SCHEMA = 'staging'
GROUP BY t.TABLE_NAME, t.TABLE_ROWS
ORDER BY t.TABLE_NAME;
