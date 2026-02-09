-- Add llm_nationality column to staging.tenants table
-- This stores LLM-predicted nationalities for records with missing data

-- Check if column already exists
SET @column_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'staging' 
      AND TABLE_NAME = 'tenants' 
      AND COLUMN_NAME = 'llm_nationality'
);

-- Add column if it doesn't exist
SET @sql = IF(
    @column_exists = 0,
    'ALTER TABLE staging.tenants ADD COLUMN llm_nationality VARCHAR(128) NULL COMMENT ''LLM-predicted nationality for records with missing data''',
    'SELECT ''Column llm_nationality already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Verify the column was added
DESCRIBE staging.tenants;
