#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}
TZ=${TZ:-Etc/UTC}

ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime
echo "$TZ" > /etc/timezone

groupadd -g "$PGID" translatarr 2>/dev/null || true
useradd -u "$PUID" -g "$PGID" -d /config -s /bin/bash -M translatarr 2>/dev/null || true

mkdir -p /config
chown -R "$PUID:$PGID" /config

exec gosu "$PUID:$PGID" "$@"
