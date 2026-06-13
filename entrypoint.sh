#!/usr/bin/env sh
set -eu

: "${HOME:=/workspace}"
: "${TTYD_CREDENTIALS:=admin:adminadmin}"
: "${TTYD_PORT:=7681}"
: "${MANAGEMENT_HOST:=0.0.0.0}"
: "${MANAGEMENT_PORT:=7680}"
: "${COMPOSE_ROOT:=/workspace/configs/docker}"
: "${STATE_FILE:=/workspace/.git-docker-tool-state.json}"
: "${PRUNE_INTERVAL_HOURS:=24}"
export HOME TTYD_CREDENTIALS TTYD_PORT MANAGEMENT_HOST MANAGEMENT_PORT COMPOSE_ROOT STATE_FILE PRUNE_INTERVAL_HOURS

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh" 2>/dev/null || true

find "$HOME/.ssh" -type f -name 'id_*' -exec chmod 600 {} \; 2>/dev/null || true

if [ -S /var/run/docker.sock ]; then
  SOCKET_GID="$(stat -c '%g' /var/run/docker.sock 2>/dev/null || true)"
  CURRENT_GID="$(id -g)"

  if [ -n "$SOCKET_GID" ] && [ "$SOCKET_GID" != "$CURRENT_GID" ]; then
    echo "Docker socket gid is $SOCKET_GID; if docker commands fail, run the container as root or with a matching runtime user/group."
  fi
else
  echo "Docker socket not found at /var/run/docker.sock. Mount it to control host containers."
fi

python3 -m app.manage_web &

if [ "$#" -eq 0 ]; then
  set -- ttyd -W -c "$TTYD_CREDENTIALS" -p "$TTYD_PORT" bash
fi

exec "$@"
