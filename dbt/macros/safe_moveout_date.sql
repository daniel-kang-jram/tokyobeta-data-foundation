{# Macro to get the integrated moveout date #}
{% macro safe_moveout_date() %}
    COALESCE(moveout_date_integrated, moveout_plans_date, moveout_date)
{% endmacro %}
