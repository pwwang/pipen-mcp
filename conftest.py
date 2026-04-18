import os

# Enable coverage collection in forked subprocesses (pytest-forked).
# Child processes check COVERAGE_PROCESS_START and call coverage.process_startup().
os.environ.setdefault("COVERAGE_PROCESS_START", "pyproject.toml")
