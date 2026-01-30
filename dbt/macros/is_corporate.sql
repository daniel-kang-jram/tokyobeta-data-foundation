{# Macro to determine if contract is corporate vs individual #}
{% macro is_corporate(contract_type_column='contract_type') %}
    CASE 
        WHEN {{ contract_type_column }} IN ({{ var('corporate_contract_types') | join(', ') }}) THEN 'corporate'
        ELSE 'individual'
    END
{% endmacro %}
