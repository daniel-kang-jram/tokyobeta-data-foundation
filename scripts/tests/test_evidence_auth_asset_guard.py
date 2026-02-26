"""Regression tests for Evidence auth background asset deploy guardrails."""

from pathlib import Path

EVIDENCE_BUILDSPEC = Path(__file__).resolve().parents[2] / "evidence/buildspec.yml"
SNAPSHOT_BUILDSPEC = Path(__file__).resolve().parents[2] / "evidence_snapshot/buildspec.yml"


def test_gold_buildspec_uploads_auth_video_explicitly() -> None:
    """Gold dashboard deploy must always publish auth video."""
    source = EVIDENCE_BUILDSPEC.read_text(encoding="utf-8")

    assert "test -f static/__auth/assets/bg.mp4" in source
    assert (
        'aws s3 cp static/__auth/assets/bg.mp4 "s3://$EVIDENCE_S3_BUCKET/__auth/assets/bg.mp4"'
        in source
    )
    assert (
        'aws s3api head-object --bucket "$EVIDENCE_S3_BUCKET" --key "__auth/assets/bg.mp4"'
        in source
    )


def test_snapshot_buildspec_uploads_auth_video_explicitly() -> None:
    """Snapshot deploy must always publish auth video."""
    source = SNAPSHOT_BUILDSPEC.read_text(encoding="utf-8")

    assert "test -f evidence_snapshot/static/__auth/assets/bg.mp4" in source
    assert (
        'aws s3 cp evidence_snapshot/static/__auth/assets/bg.mp4 '
        '"s3://$EVIDENCE_S3_BUCKET/__auth/assets/bg.mp4"'
    ) in source
    assert (
        'aws s3api head-object --bucket "$EVIDENCE_S3_BUCKET" --key "__auth/assets/bg.mp4"'
        in source
    )
