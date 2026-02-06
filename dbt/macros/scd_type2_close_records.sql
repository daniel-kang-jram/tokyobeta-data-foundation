{% macro scd_type2_close_records(table_name, id_column) %}
    /*
    Macro to close out previous SCD Type 2 records when new ones are inserted.
    Updates valid_to and is_current for superseded records.
    
    Args:
        table_name: Name of the SCD table
        id_column: Primary identifier column (e.g., 'tenant_id')
    */
    
    -- Close out previous records where a new record exists
    UPDATE {{ table_name }} old_rec
    SET 
        valid_to = new_rec.valid_from - INTERVAL 1 DAY,
        is_current = FALSE
    FROM (
        SELECT 
            {{ id_column }},
            MIN(valid_from) as valid_from
        FROM {{ table_name }}
        WHERE is_current = TRUE
        GROUP BY {{ id_column }}
    ) new_rec
    WHERE old_rec.{{ id_column }} = new_rec.{{ id_column }}
    AND old_rec.is_current = TRUE
    AND old_rec.valid_from < new_rec.valid_from;
    
{% endmacro %}
