"""Regression tests for terraform secrets module invariants."""

from pathlib import Path

SECRETS_MAIN_TF = (
    Path(__file__).resolve().parents[2] / "terraform/modules/secrets/main.tf"
)


def test_rds_cron_preconditions_gate_on_secret_creation_flag() -> None:
    """Both cron secret preconditions must apply when secret creation is enabled."""
    source = SECRETS_MAIN_TF.read_text(encoding="utf-8")

    # Two preconditions protect required connection fields and password policy.
    assert source.count("!var.create_rds_cron_secret") >= 2
