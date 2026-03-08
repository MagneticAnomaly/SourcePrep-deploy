import pytest
import sys

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", "-s", "tests/test_pipeline_orchestrator.py::TestFastSync::test_run_fast_sync_starts"]))
