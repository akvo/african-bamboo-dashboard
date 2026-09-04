#!/usr/bin/env bash
set -e
pip -q install --upgrade pip && \
pip -q install --no-cache-dir -r requirements.txt && \
pip check
# Wait for the backend to finish migrating: qcluster dies
# immediately if django_q's tables do not exist yet. Use
# --check rather than migrate so two containers never race.
for i in $(seq 1 30); do
  if python manage.py migrate --check >/dev/null 2>&1; then
    break
  fi
  echo "waiting for migrations ($i/30)"
  sleep 5
done

python manage.py qcluster
