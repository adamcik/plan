#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage:
  $0 [options]

Options:
  --instance <name>     Instance name (default: ntnu)
  --image <ref>         Image ref to run (default: runtime image of --container)
  --container <name>    Existing runtime container name (default: plan-<instance>)
  --env-file <path>     Env file for migration run (default: /etc/plan/<instance>.env)
  --no-mount-state      Do not mount /var/lib/plan and /var/cache/plan
  --show-plan           Show migration plan
  --check               Run migrate --check
  --apply               Apply migrations (explicitly required)
  -h, --help            Show this help

Examples:
  $0                     # default: show plan + check
  $0 --show-plan --check
  $0 --image ghcr.io/adamcik/plan:latest
  $0 --apply --image ghcr.io/adamcik/plan:latest
EOF
}

DEFAULT_INSTANCE_NAME="ntnu"
INSTANCE_NAME="$DEFAULT_INSTANCE_NAME"
IMAGE_REF=""
CONTAINER_NAME=""
ENV_FILE=""
MOUNT_STATE=1
SHOW_PLAN=1
CHECK_ONLY=1
APPLY=0
CHECK_SET=0
LIB_DIR=""
CACHE_DIR=""

CONTAINER_SET=0
ENV_FILE_SET=0

apply_instance_defaults() {
  if [ -z "$CONTAINER_NAME" ] || [ "$CONTAINER_SET" -eq 0 ]; then
    CONTAINER_NAME="plan-${INSTANCE_NAME}"
  fi

  if [ -z "$ENV_FILE" ] || [ "$ENV_FILE_SET" -eq 0 ]; then
    ENV_FILE="/etc/plan/${INSTANCE_NAME}.env"
  fi

  LIB_DIR="/var/lib/plan/${INSTANCE_NAME}"
  CACHE_DIR="/var/cache/plan/${INSTANCE_NAME}"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --instance)
      INSTANCE_NAME="$2"
      shift 2
      ;;
    --image)
      IMAGE_REF="$2"
      shift 2
      ;;
    --container)
      CONTAINER_NAME="$2"
      CONTAINER_SET=1
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      ENV_FILE_SET=1
      shift 2
      ;;
    --no-mount-state)
      MOUNT_STATE=0
      shift
      ;;
    --show-plan)
      SHOW_PLAN=1
      shift
      ;;
    --check)
      CHECK_ONLY=1
      CHECK_SET=1
      shift
      ;;
    --apply)
      APPLY=1
      if [ "$CHECK_SET" -eq 0 ]; then
        CHECK_ONLY=0
      fi
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

apply_instance_defaults

log() {
  printf '\n==> %s\n' "$*"
}

if [ -z "$IMAGE_REF" ]; then
  if ! sudo podman container exists "$CONTAINER_NAME"; then
    echo "Container does not exist: $CONTAINER_NAME" >&2
    echo "Pass --image explicitly or use an existing --container." >&2
    exit 1
  fi
  IMAGE_REF="$(sudo podman inspect "$CONTAINER_NAME" --format '{{.ImageName}}')"
fi

if ! sudo test -f "$ENV_FILE"; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

log "Migration runner image"
echo "ImageRef: $IMAGE_REF"
echo "EnvFile:  $ENV_FILE"
echo "LibDir:   $LIB_DIR"
echo "CacheDir: $CACHE_DIR"

run_args=(
  --rm
  --network host
  --user 33:33
  --env-file "$ENV_FILE"
)

if [ "$MOUNT_STATE" -eq 1 ]; then
  sudo install -d -o www-data -g www-data -m 0750 "$LIB_DIR"
  sudo install -d -o www-data -g www-data -m 0750 "$CACHE_DIR"
  run_args+=(
    -v "$LIB_DIR":/var/lib/plan:rw,nosuid,nodev,noexec
    -v "$CACHE_DIR":/var/cache/plan:rw,nosuid,nodev,noexec
  )
fi

if [ "$SHOW_PLAN" -eq 1 ]; then
  log "Show migration plan"
  sudo podman run "${run_args[@]}" "$IMAGE_REF" /bin/manage showmigrations --plan
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  log "Check unapplied migrations"
  sudo podman run "${run_args[@]}" "$IMAGE_REF" /bin/manage migrate --check --noinput
fi

if [ "$APPLY" -eq 1 ]; then
  log "Apply migrations"
  sudo podman run "${run_args[@]}" "$IMAGE_REF" /bin/manage migrate --noinput
fi

if [ "$SHOW_PLAN" -eq 0 ] && [ "$CHECK_ONLY" -eq 0 ] && [ "$APPLY" -eq 0 ]; then
  echo "Nothing to do. Use --show-plan, --check, and/or --apply." >&2
  exit 2
fi

log "Done"
