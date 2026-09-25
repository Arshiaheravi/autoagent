"""Session worker — claim→run→mark lifecycle, tenant scoping, hard loop cap."""
import pytest

import job_queue
import provisioning
import session_worker


def test_run_once_empty_queue_returns_none():
    assert session_worker.run_once(execute=lambda j: True) is None


def test_run_once_marks_done_on_success():
    jid = job_queue.enqueue("acme", project="shop")
    job = session_worker.run_once(execute=lambda j: True)
    assert job["job_id"] == jid
    assert job["status"] == job_queue.STATUS_DONE


def test_run_once_marks_failed_on_failure():
    job_queue.enqueue("acme", project="shop")
    job = session_worker.run_once(execute=lambda j: False)
    assert job["status"] == job_queue.STATUS_FAILED


def test_run_once_marks_failed_when_execute_raises():
    job_queue.enqueue("acme", project="shop")
    def boom(j):
        raise RuntimeError("kaboom")
    job = session_worker.run_once(execute=boom)   # must not propagate
    assert job["status"] == job_queue.STATUS_FAILED


def test_execute_passes_tenant_env(monkeypatch):
    provisioning.provision_tenant("acme")
    captured = {}
    def fake_run(argv, env=None, timeout=None):
        captured["argv"] = argv
        captured["env"] = env
        class R: returncode = 0
        return R()
    monkeypatch.setattr(session_worker.subprocess, "run", fake_run)
    job = job_queue.get_job(job_queue.enqueue("acme", project="shop", session_type="work"))
    assert session_worker.execute_job(job) is True
    assert captured["env"]["AUTOAGENT_TENANT_ID"] == "acme"
    assert captured["env"]["AUTOAGENT_HOME"] == provisioning.get_tenant("acme").data_root
    assert captured["argv"][:3] == ["autoagent", "run", "shop"]
    assert "--type" in captured["argv"]


def test_execute_rejects_inactive_tenant(monkeypatch):
    # no such tenant registered
    job = {"job_id": "x", "tenant_id": "ghost", "project": "shop"}
    assert session_worker.execute_job(job) is False


def test_run_forever_has_hard_cap():
    for _ in range(5):
        job_queue.enqueue("acme", project="shop")
    n = session_worker.run_forever(max_iterations=3, execute=lambda j: True)
    assert n == 3                                   # stopped at the cap, not drained
    assert sum(1 for j in job_queue.list_jobs() if j["status"] == job_queue.STATUS_QUEUED) == 2


def test_run_forever_stops_on_empty():
    job_queue.enqueue("acme", project="shop")
    n = session_worker.run_forever(max_iterations=100, execute=lambda j: True)
    assert n == 1                                   # only one job existed


def test_run_forever_rejects_nonpositive_cap():
    with pytest.raises(ValueError):
        session_worker.run_forever(max_iterations=0)
