from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_postgres_password_is_external_and_required():
    compose = (ROOT / "docker-compose.yml").read_text()

    expected_password = (
        "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}"
    )
    assert expected_password in compose
    assert "POSTGRES_PASSWORD:-" not in compose
    assert "DATABASE_URL:" in compose


def test_ci_pipelines_do_not_define_postgres_password():
    workflows = ROOT.joinpath(".github", "workflows")

    for workflow in workflows.glob("*.yml"):
        assert "POSTGRES_PASSWORD" not in workflow.read_text()
