"""Session job queue — enqueue/inspect/claim, tenant-scoped."""
import pytest

import job_queue


def test_enqueue_and_get():
    jid = job_queue.enqueue("acme", project="shop", session_type="work")
    job = job_queue.get_job(jid)
    assert job["tenant_id"] == "acme"
    assert job["project"] == "shop"
    assert job["status"] == job_queue.STATUS_QUEUED


def test_list_is_tenant_scoped():
    job_queue.enqueue("acme")
    job_queue.enqueue("globex")
    assert {j["tenant_id"] for j in job_queue.list_jobs("acme")} == {"acme"}
    assert len(job_queue.list_jobs()) == 2


def test_claim_next_is_fifo_and_marks_running():
    a = job_queue.enqueue("acme")
    b = job_queue.enqueue("acme")
    claimed = job_queue.claim_next()
    assert claimed["job_id"] == a          # oldest first
    assert claimed["status"] == job_queue.STATUS_RUNNING
    assert job_queue.get_job(b)["status"] == job_queue.STATUS_QUEUED


def test_mark_and_missing():
    jid = job_queue.enqueue("acme")
    job_queue.mark(jid, job_queue.STATUS_DONE)
    assert job_queue.get_job(jid)["status"] == job_queue.STATUS_DONE
    assert job_queue.get_job("nope") is None


def test_invalid_tenant_rejected():
    with pytest.raises(ValueError):
        job_queue.enqueue("../evil")
