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


def test_rds_cron_preconditions_gate_on_secret_creation_flag() -> None:
    """Both cron secret preconditions must apply when secret creation is enabled."""
    source = SECRETS_MAIN_TF.read_text(encoding="utf-8")

    # Two preconditions protect required connection fields and password policy.
    assert source.count("!var.create_rds_cron_secret") >= 2


def test_prod_defaults_disable_cron_secret_creation() -> None:
    """Production variables must disable cron secret creation by default."""
    source = PROD_VARIABLES_TF.read_text(encoding="utf-8")

    block = source.split('variable "create_rds_cron_secret"')[1].split("}", 1)[0]
    assert "default     = false" in block


def test_deploy_workflow_enforces_cron_secret_creation_disabled() -> None:
    """Deploy workflow must explicitly pass create_rds_cron_secret=false."""
    source = DEPLOY_WORKFLOW_YML.read_text(encoding="utf-8")

    assert 'TF_VAR_create_rds_cron_secret: "false"' in source
    assert 'TF_VAR_create_rds_cron_secret must be false in production.' in source
