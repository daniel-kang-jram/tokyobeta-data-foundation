{# Macro to get the integrated moveout date #}
{% macro safe_moveout_date(table_alias='') %}
    {% if table_alias %}
        COALESCE({{ table_alias }}.moveout_date_integrated, {{ table_alias }}.moveout_plans_date, {{ table_alias }}.moveout_date)
    {% else %}
        COALESCE(moveout_date_integrated, moveout_plans_date, moveout_date)
    {% endif %}
{% endmacro %}
