# Інструмент: Copilot; Claude — перевірка непривілейованого USER у Dockerfile.
# Застосування: регресійні перевірки секретів, безпечного встановлення залежностей
# і запуску контейнера API не від root.
# Верифікація: тести пройшли локально; тест USER падав до зміни Dockerfile.

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


def test_dependency_installations_require_binary_wheels():
    files = [
        ROOT / ".github" / "workflows" / "ci.yml",
        ROOT / ".github" / "workflows" / "deploy-api-docs.yml",
        ROOT / ".github" / "workflows" / "static-analysis.yml",
        ROOT / "Dockerfile",
    ]

    for path in files:
        text = path.read_text()
        for line in text.splitlines():
            if "pip install" in line and "-r " in line:
                assert "--only-binary=:all:" in line, path


def test_api_container_runs_as_non_root_user():
    lines = (ROOT / "Dockerfile").read_text().splitlines()
    instructions = [line.split(maxsplit=1) for line in lines if line[:1].isupper()]
    keywords = [parts[0] for parts in instructions]
    assert "USER" in keywords, "Dockerfile must switch to a non-root USER"

    last_user = len(keywords) - 1 - keywords[::-1].index("USER")
    assert last_user < keywords.index("CMD")
    assert instructions[last_user][1].strip() not in {"root", "0", "0:0"}
