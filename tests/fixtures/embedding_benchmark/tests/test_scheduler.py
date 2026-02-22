"""Tests for the background task scheduler."""


def test_add_job_creates_pending_job():
    from src.scheduler import TaskScheduler, JobStatus
    sched = TaskScheduler()
    job = sched.add_job("j1", "cleanup", lambda: None, interval_seconds=300)
    assert job.status == JobStatus.PENDING


def test_run_job_executes_and_completes():
    from src.scheduler import TaskScheduler, JobStatus
    executed = []
    sched = TaskScheduler()
    sched.add_job("j1", "task", lambda: executed.append(1), interval_seconds=60)
    assert sched.run_job("j1") is True
    assert len(executed) == 1


def test_cancel_job_prevents_execution():
    from src.scheduler import TaskScheduler
    sched = TaskScheduler()
    sched.add_job("j1", "task", lambda: None, interval_seconds=60)
    sched.cancel_job("j1")
    assert sched.run_job("j1") is False


def test_failed_job_records_error():
    from src.scheduler import TaskScheduler, JobStatus
    def failing():
        raise RuntimeError("boom")
    sched = TaskScheduler()
    sched.add_job("j1", "bad", failing, interval_seconds=60)
    sched.run_job("j1")
    status = sched.get_status()
    assert status[0]["status"] == "failed"
