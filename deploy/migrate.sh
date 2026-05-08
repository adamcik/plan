#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  deploy/migrate.sh [options]

Options:
  --image <ref>         Image ref to run (default: runtime image of --container)
  --container <name>    Existing runtime container name (default: plan-ntnu)
  --env-file <path>     Env file for migration run (default: /etc/plan/env)
  --no-mount-state      Do not mount /var/lib/plan and /var/cache/plan
  --show-plan           Show migration plan before applying
  --check               Run migrate --check only (no apply)
  -h, --help            Show this help

Examples:
  deploy/migrate.sh
  deploy/migrate.sh --show-plan
  deploy/migrate.sh --image ghcr.io/adamcik/plan:latest
  deploy/migrate.sh --check
EOF
}

IMAGE_REF=""
CONTAINER_NAME="plan-ntnu"
ENV_FILE="/etc/plan/env"
MOUNT_STATE=1
SHOW_PLAN=0
CHECK_ONLY=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --image)
      IMAGE_REF="$2"
      shift 2
      ;;
    --container)
      CONTAINER_NAME="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
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

run_args=(
  --rm
  --network host
  --user 33:33
  --env-file "$ENV_FILE"
)

if [ "$MOUNT_STATE" -eq 1 ]; then
  sudo install -d -o www-data -g www-data -m 0750 /var/lib/plan
  sudo install -d -o www-data -g www-data -m 0750 /var/cache/plan
  run_args+=(
    -v /var/lib/plan:/var/lib/plan:rw,nosuid,nodev,noexec
    -v /var/cache/plan:/var/cache/plan:rw,nosuid,nodev,noexec
  )
fi

if [ "$SHOW_PLAN" -eq 1 ]; then
  log "Show migration plan"
  sudo podman run "${run_args[@]}" "$IMAGE_REF" /bin/manage showmigrations --plan
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  log "Check unapplied migrations"
  sudo podman run "${run_args[@]}" "$IMAGE_REF" /bin/manage migrate --check --noinput
else
  log "Apply migrations"
  sudo podman run "${run_args[@]}" "$IMAGE_REF" /bin/manage migrate --noinput
fi

log "Done"
