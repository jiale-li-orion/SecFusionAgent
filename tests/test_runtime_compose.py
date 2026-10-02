from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_long_lived_runtime_owns_task_event_plane_processes() -> None:
    compose = (ROOT / "deploy/docker-compose.yml").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "task-event-dispatcher:" in compose
    assert 'command: ["python", "-m", "apps.worker.task_event_dispatcher"]' in compose
    assert "task-event-scheduler:" in compose
    assert 'command: ["python", "-m", "apps.worker.task_event_scheduler"]' in compose

    runtime_up = makefile.split("dev-runtime-up:", 1)[1].split("# Long-lived", 1)[0]
    assert "task-event-dispatcher" in runtime_up
    assert "task-event-scheduler" in runtime_up

    runtime_status = makefile.split("data-plane-status:", 1)[1].split(
        "data-plane-metrics:", 1
    )[0]
    assert "task-event-dispatcher" in runtime_status
    assert "task-event-scheduler" in runtime_status
