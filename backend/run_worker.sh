#!/usr/bin/env bash
set -e
pip -q install --upgrade pip && \
pip -q install --no-cache-dir -r requirements.txt && \
pip check
python manage.py qcluster
