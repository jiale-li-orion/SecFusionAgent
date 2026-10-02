#!/bin/sh
set -eu

if [ "${SECFUSION_ARTIFACT_STORE_BACKEND:-filesystem}" = "filesystem" ]; then
  root="${SECFUSION_ARTIFACT_ROOT:-/var/lib/secfusion/artifacts}"
  bucket="${SECFUSION_S3_BUCKET:-secfusion-evidence}"
  probe_dir="$root/$bucket/sha256"
  mkdir -p "$probe_dir"
  probe="$probe_dir/.runtime-write-probe.$$"
  if ! ( : >"$probe" ) 2>/dev/null; then
    echo "artifact store is not writable by the runtime user: $probe_dir" >&2
    exit 1
  fi
  rm -f "$probe"
fi

exec "$@"
