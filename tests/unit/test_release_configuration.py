from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_production_deployment_starts_celery_beat_scheduler() -> None:
    deploy_script = (ROOT / "scripts" / "deploy_prod.sh").read_text(encoding="utf-8")

    assert 'up -d backend worker scheduler frontend nginx prometheus grafana backup' in deploy_script


def test_release_pipeline_publishes_all_runtime_images() -> None:
    release_workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    for image in ("kravigil-backend", "kravigil-worker", "kravigil-network-engine", "kravigil-frontend"):
        assert f"ghcr.io/${{ github.repository }}/{image}" in release_workflow

    assert "name: Build and push Frontend" in release_workflow
    assert "context: ./frontend" in release_workflow
    assert "file: ./frontend/Dockerfile" in release_workflow
