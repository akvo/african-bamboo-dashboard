#!/usr/bin/env bash
#shellcheck disable=SC3040

set -euo pipefail

# A killed test run exits 137 (128 + SIGKILL) and prints nothing
# useful, so it reads as a hang or a mystery failure. Name it.
on_exit () {
    code=$?
    if [ "${code}" -eq 137 ]; then
        echo ""
        echo "=============================================="
        echo "Tests were KILLED (exit 137) — this is almost"
        echo "always the OOM killer, not a test failure."
        echo ""
        echo "Each parallel worker is a full Django process,"
        echo "and coverage keeps per-process trace data for"
        echo "every test until 'coverage combine' runs."
        echo ""
        echo "Retry with fewer workers:"
        echo "    TEST_PARALLEL=1 ./test.sh"
        echo "=============================================="
    fi
    exit "${code}"
}
trap on_exit EXIT

# Reinstalling on every run costs 10-30s even fully cached.
# Skip when requirements.txt has not changed since the last
# successful install. REQUIREMENTS_FORCE=1 overrides.
REQ_STAMP=".pip/.requirements.sha256"
REQ_HASH="$(sha256sum requirements.txt | cut -d" " -f1)"
if [ "${REQUIREMENTS_FORCE:-0}" = "1" ] \
   || [ ! -f "${REQ_STAMP}" ] \
   || [ "$(cat "${REQ_STAMP}")" != "${REQ_HASH}" ]; then
    pip -q install --upgrade pip
    pip -q install --cache-dir=.pip -r requirements.txt
    mkdir -p .pip
    echo "${REQ_HASH}" > "${REQ_STAMP}"
else
    echo "requirements.txt unchanged — skipping pip install"
fi

./manage.py migrate --noinput

# Parallelism follows the host instead of a hardcoded 4.
# GitHub's ubuntu-latest has 2 cores and ~7GB RAM: forking 4
# workers there burns memory without buying speed, and the
# resulting OOM kill looks like a hang. Capped at 4 so a big
# dev machine does not spawn a worker per core.
if [ -n "${TEST_PARALLEL:-}" ]; then
    PARALLEL="${TEST_PARALLEL}"
else
    CORES="$(nproc 2>/dev/null || echo 2)"
    PARALLEL="$(( CORES < 4 ? CORES : 4 ))"
fi

# --noinput matters: a run killed part-way leaves its test
# databases behind, and without it the next run stops on an
# interactive "Type 'yes' to delete" prompt. In CI, or any
# non-tty, that hangs until the job times out.
echo "Running tests (parallel=${PARALLEL})"
COVERAGE_PROCESS_START=./.coveragerc \
  coverage run --parallel-mode --concurrency=multiprocessing \
  --rcfile=./.coveragerc \
  ./manage.py test --shuffle --noinput \
  --parallel "${PARALLEL}" \
  "$@"

echo "Coverage"
coverage combine --rcfile=./.coveragerc
coverage report -m --rcfile=./.coveragerc
coverage lcov --rcfile=./.coveragerc -o coverage.lcov

echo "Generate Django DBML"
./manage.py dbml > db.dbml
echo "Done"

flake8
