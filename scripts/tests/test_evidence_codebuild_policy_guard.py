"""Guardrails for Evidence hosting CodeBuild IAM permissions."""

from pathlib import Path


MODULE_MAIN_TF = (
    Path(__file__).resolve().parents[2] / "terraform/modules/evidence_hosting/main.tf"
)


def test_codebuild_site_bucket_policy_includes_read_for_verification() -> None:
    """CodeBuild must read site objects to run post-upload verification checks."""
    source = MODULE_MAIN_TF.read_text(encoding="utf-8")

    site_bucket_anchor = 'aws_s3_bucket.site.arn,\n          "${aws_s3_bucket.site.arn}/*"'
    assert site_bucket_anchor in source

    statement_start = source.rfind("{", 0, source.index(site_bucket_anchor))
    statement_end = source.index("}", source.index(site_bucket_anchor))
    statement = source[statement_start:statement_end]

    assert '"s3:GetObject"' in statement
