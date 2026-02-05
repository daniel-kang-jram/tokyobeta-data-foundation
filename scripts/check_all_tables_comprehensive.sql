-- Generate queries to check all staging tables for recent activity
-- This creates a dynamic query for each table based on its date columns

SET @cutoff_date = DATE_SUB(CURDATE(), INTERVAL 1 YEAR);
SET SESSION group_concat_max_len = 100000;

-- Get the list of all tables with their date columns
SELECT 
    t.TABLE_NAME,
    COALESCE(
        GROUP_CONCAT(
            DISTINCT c.COLUMN_NAME 
            ORDER BY c.ORDINAL_POSITION 
            SEPARATOR ','
        ),
        'NO_DATE_COLUMNS'
    ) as date_columns,
    t.TABLE_ROWS as approx_rows
FROM information_schema.TABLES t
LEFT JOIN information_schema.COLUMNS c 
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA 
    AND t.TABLE_NAME = c.TABLE_NAME
    AND c.DATA_TYPE IN ('date', 'datetime', 'timestamp')
WHERE t.TABLE_SCHEMA = 'staging'
GROUP BY t.TABLE_NAME, t.TABLE_ROWS
ORDER BY t.TABLE_NAME;
