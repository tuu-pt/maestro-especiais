#!/bin/sh
# pytest in a Linux container on the compose network (make test-docker), for machines where the
# local .venv cannot load libpq (e.g. Windows Smart App Control blocks the psycopg-binary DLL).
# The repository is mounted at /repo and copied without the host .venv and node_modules; a report
# asked with --annex-c-report=<path> is copied back to the repository.
set -e
apt-get update -qq >/dev/null && apt-get install -y -qq git >/dev/null
# LibreOffice for the fidelity check of the exported .docx (Phase 6); SKIP_LIBREOFFICE=1 to skip
if [ -z "$SKIP_LIBREOFFICE" ]; then
  apt-get install -y -qq --no-install-recommends libreoffice-writer-nogui libreoffice-calc-nogui fonts-dejavu-core fonts-crosextra-carlito fonts-liberation2 >/dev/null
fi
mkdir -p /work
tar -C /repo --exclude=./.venv --exclude=./frontend/node_modules --exclude=./frontend/test-results \
    -cf - . | tar -C /work -xf -
cd /work
python -m venv /venv
/venv/bin/pip install -q --upgrade pip
/venv/bin/pip install -q -e "backend[dev]" -r tools/requirements.txt
# The credentials stay in the container: read from .env, never printed.
user=$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2- | tr -d '\r')
password=$(grep -E '^POSTGRES_PASSWORD=' .env | cut -d= -f2- | tr -d '\r')
export TEST_DATABASE_URL="postgresql+psycopg://${user}:${password}@db:5432/maestro_test"
status=0
/venv/bin/python -m pytest -p no:cacheprovider "$@" || status=$?
for arg in "$@"; do
  case "$arg" in
    --annex-c-report=*) report="${arg#*=}"; cp "/work/$report" "/repo/$report" ;;
    --fichas-report=*) report="${arg#*=}"; cp "/work/$report" "/repo/$report" ;;
  esac
done
exit $status
