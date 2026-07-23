#!/bin/bash

# Root-owned launcher for the dedicated AWARE Jupyter kernel on VAST.
# Untrusted Python begins only after filesystem isolation, UID/GID drop,
# capability removal, and no_new_privs activation.

set -Eeuo pipefail

readonly PROJECT_ROOT="/mnt/data/Son/notebook/AWARE"
readonly VENV_ROOT="${PROJECT_ROOT}/.venv"
readonly VENV_PYTHON="${VENV_ROOT}/bin/python"
readonly SANDBOX_RUNTIME="${PROJECT_ROOT}/.vast/runtime"
readonly HOST_JUPYTER_RUNTIME="/root/.local/share/jupyter/runtime"
readonly TRAIN_UID="999"
readonly TRAIN_GID="989"

fail() {
  printf 'aware-isolated-kernel: %s\n' "$1" >&2
  exit 64
}

[[ "${EUID}" -eq 0 ]] || fail "launcher must be started by root Jupyter"
[[ "$#" -eq 2 ]] || fail "expected only: -f CONNECTION_FILE"
[[ "$1" == "-f" ]] || fail "first argument must be -f"
[[ -d "${PROJECT_ROOT}" ]] || fail "project root missing"
[[ -x "${VENV_PYTHON}" ]] || fail "venv Python missing"

host_connection="$(readlink -f -- "$2")"
case "${host_connection}" in
  "${HOST_JUPYTER_RUNTIME}"/kernel-*.json) ;;
  *) fail "connection file is outside approved Jupyter runtime" ;;
esac
[[ -f "${host_connection}" ]] || fail "connection file missing"

/usr/bin/install -d -o "${TRAIN_UID}" -g "${TRAIN_GID}" -m 0700 \
  "${SANDBOX_RUNTIME}"

connection_name="$(basename -- "${host_connection}")"
sandbox_connection="${SANDBOX_RUNTIME}/${connection_name}"
[[ ! -e "${sandbox_connection}" ]] || fail "sandbox connection file already exists"

/usr/bin/install -o "${TRAIN_UID}" -g "${TRAIN_GID}" -m 0600 \
  "${host_connection}" "${sandbox_connection}"

cleanup() {
  /usr/bin/rm -f -- "${sandbox_connection}"
}
trap cleanup EXIT

set +e
/usr/bin/bwrap \
  --die-with-parent \
  --new-session \
  --unshare-pid \
  --unshare-ipc \
  --unshare-uts \
  --ro-bind /usr /usr \
  --symlink usr/bin /bin \
  --symlink usr/lib /lib \
  --symlink usr/lib64 /lib64 \
  --dev /dev \
  --perms 0666 --mknod c 195 0 /dev/nvidia0 \
  --perms 0666 --mknod c 195 255 /dev/nvidiactl \
  --perms 0666 --mknod c 509 0 /dev/nvidia-uvm \
  --perms 0666 --mknod c 509 1 /dev/nvidia-uvm-tools \
  --proc /proc \
  --dir /etc \
  --ro-bind-try /etc/ld.so.cache /etc/ld.so.cache \
  --ro-bind-try /etc/ssl /etc/ssl \
  --ro-bind-try /etc/resolv.conf /etc/resolv.conf \
  --ro-bind-try /etc/hosts /etc/hosts \
  --ro-bind-try /etc/nsswitch.conf /etc/nsswitch.conf \
  --dir /mnt \
  --dir /mnt/data \
  --dir /mnt/data/Son \
  --dir /mnt/data/Son/notebook \
  --bind "${PROJECT_ROOT}" "${PROJECT_ROOT}" \
  --ro-bind "${VENV_ROOT}" "${VENV_ROOT}" \
  --dir /var \
  --symlink "${PROJECT_ROOT}/.vast/tmp" /tmp \
  --symlink "${PROJECT_ROOT}/.vast/tmp" /var/tmp \
  --ro-bind /dev/null /usr/bin/python3.12 \
  --chdir "${PROJECT_ROOT}" \
  /usr/bin/setpriv \
  --reuid "${TRAIN_UID}" \
  --regid "${TRAIN_GID}" \
  --clear-groups \
  --no-new-privs \
  --bounding-set=-all \
  --inh-caps=-all \
  --ambient-caps=-all \
  /usr/bin/env -i \
  HOME="${PROJECT_ROOT}/.train-home" \
  USER=train \
  LOGNAME=train \
  SHELL=/bin/bash \
  VIRTUAL_ENV="${VENV_ROOT}" \
  PATH="${VENV_ROOT}/bin:/usr/local/cuda/bin:/usr/bin:/bin" \
  LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu \
  PYTHONNOUSERSITE=1 \
  PIP_REQUIRE_VIRTUALENV=true \
  TMPDIR="${PROJECT_ROOT}/.vast/tmp" \
  JUPYTER_RUNTIME_DIR="${SANDBOX_RUNTIME}" \
  PROJECT_CODE_ROOT="${PROJECT_ROOT}" \
  PROJECT_DATA_ROOT="${PROJECT_ROOT}/.vast/data" \
  PROJECT_OUTPUT_ROOT="${PROJECT_ROOT}/.vast/output" \
  CUDA_VISIBLE_DEVICES=0 \
  NVIDIA_VISIBLE_DEVICES=0 \
  "${VENV_PYTHON}" -m ipykernel_launcher -f "${sandbox_connection}"
kernel_status=$?
set -e

exit "${kernel_status}"
