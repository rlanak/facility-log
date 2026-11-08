#!/bin/sh
# The app never runs as root (security, 08/11/2026). Started as root only to
# hand the data volume to the app user — a bind-mounted ./data-docker is
# created root-owned by Docker, and older versions wrote it as root — then
# the process drops to that user for good.
set -e
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$FACILITY_LOG_DATA_DIR"
    chown -R app:app "$FACILITY_LOG_DATA_DIR"
    exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
