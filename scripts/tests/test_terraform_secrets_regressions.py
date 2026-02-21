"""Regression tests for terraform secrets module invariants."""

from pathlib import Path

SECRETS_MAIN_TF = (
    Path(__file__).resolve().parents[2] / "terraform/modules/secrets/main.tf"
)
PROD_VARIABLES_TF = (
    Path(__file__).resolve().parents[2] / "terraform/environments/prod/variables.tf"
)
DEPLOY_WORKFLOW_YML = (
    Path(__file__).resolve().parents[2] / ".github/workflows/deploy-prod.yml"
)


def test_rds_cron_preconditions_gate_on_secret_value_management_flag() -> None:
    """Cron secret preconditions should trigger only when Terraform manages secret values."""
    source = SECRETS_MAIN_TF.read_text(encoding="utf-8")

    # Two preconditions protect required connection fields and password policy.
    assert source.count("!var.manage_rds_cron_secret_value") >= 2


def test_rds_cron_secret_version_requires_value_management_flag() -> None:
    """Terraform must not create cron secret versions when value management is disabled."""
    source = SECRETS_MAIN_TF.read_text(encoding="utf-8")

    assert "count     = var.create_rds_cron_secret && var.manage_rds_cron_secret_value ? 1 : 0" in source


def test_prod_defaults_keep_cron_secret_creation_enabled() -> None:
    """Production defaults should preserve existing cron secret resources in state."""
    source = PROD_VARIABLES_TF.read_text(encoding="utf-8")

    block = source.split('variable "create_rds_cron_secret"')[1].split("}", 1)[0]
    assert "default     = true" in block


def test_deploy_workflow_enforces_safe_cron_secret_flags() -> None:
    """Deploy workflow must preserve secret resource and freeze secret value mutation."""
    source = DEPLOY_WORKFLOW_YML.read_text(encoding="utf-8")

    assert 'TF_VAR_create_rds_cron_secret: "true"' in source
    assert 'TF_VAR_create_rds_cron_secret must be true in production.' in source
    assert 'TF_VAR_manage_rds_cron_secret_value: "false"' in source


def test_deploy_workflow_imports_existing_prod_cron_secret_before_plan() -> None:
    """Deploy workflow should import existing prod cron secret into state when missing."""
    source = DEPLOY_WORKFLOW_YML.read_text(encoding="utf-8")

    assert "Import existing prod cron secret into Terraform state" in source
    assert "tokyobeta/prod/rds/cron-credentials" in source
    assert "module.secrets.aws_secretsmanager_secret.rds_cron_credentials[0]" in source
    assert 'grep -Fqx "${CRON_SECRET_ADDR}"' in source
