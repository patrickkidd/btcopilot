import os.path

from click.testing import CliRunner

from btcopilot import commands, create_app


def test_ingest(tmp_path):
    SOURCE_DIR = os.path.join(os.path.dirname(__file__), "data")
    runner = CliRunner()
    app = create_app()
    with app.app_context():
        result = runner.invoke(
            commands.ingest,
            ["--sources-dir", SOURCE_DIR, "--data-dir", os.path.join(tmp_path, "data")],
        )
    assert result.exit_code == 0
