#!/usr/bin/env sh
set -eu

mkdir -p /workspace/.ssh
chmod 700 /workspace/.ssh 2>/dev/null || true

if [ ! -e /root/.ssh ] || [ -L /root/.ssh ]; then
  ln -sfn /workspace/.ssh /root/.ssh
fi

find /workspace/.ssh -type f -name 'id_*' -exec chmod 600 {} \; 2>/dev/null || true

if [ -S /var/run/docker.sock ]; then
  SOCKET_GID="$(stat -c '%g' /var/run/docker.sock 2>/dev/null || true)"
  CURRENT_GID="$(id -g)"

  if [ -n "$SOCKET_GID" ] && [ "$SOCKET_GID" != "$CURRENT_GID" ]; then
    echo "Docker socket gid is $SOCKET_GID; if docker commands fail, run the container as root or with a matching runtime user/group."
  fi
else
  echo "Docker socket not found at /var/run/docker.sock. Mount it to control host containers."
fi

if [ "$#" -eq 0 ]; then
  exec tail -f /dev/null
fi

exec "$@"
