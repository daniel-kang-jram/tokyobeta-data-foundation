import pathlib


def test_ggh_datatransit_uses_non_locking_mysqldump_flags():
    script_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "example_cron_scripts"
        / "ggh_datatransit.sh"
    )
    content = script_path.read_text(encoding="utf-8")

    assert "--single-transaction" in content
    assert "--quick" in content
    assert "--lock-tables=false" in content
