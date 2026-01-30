{# Macro to convert string 'NULL' and '--' to SQL NULL #}
{% macro clean_string_null(column_name) %}
    CASE 
        WHEN {{ column_name }} IN ('NULL', '--', 'null', '') THEN NULL
        ELSE {{ column_name }}
    END
{% endmacro %}
