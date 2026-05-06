#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  deploy/upgrade.sh [options]

Options:
  --image <ref>       Image ref to pull (default: ghcr.io/adamcik/plan:latest)
  --unit <name>       systemd unit (default: container-plan-ntnu.service)
  --container <name>  container name (default: plan-ntnu)
  --env-file <path>   env file for --recreate (default: /etc/plan/env)
  --recreate          Recreate container + regenerate systemd unit
  --check             Pull and compare only; do not restart/recreate
  -h, --help          Show this help

Examples:
  deploy/upgrade.sh
  deploy/upgrade.sh --image ghcr.io/adamcik/plan@sha256:abcd...
  deploy/upgrade.sh --recreate
EOF
}

IMAGE_REF="ghcr.io/adamcik/plan:latest"
UNIT_NAME="container-plan-ntnu.service"
CONTAINER_NAME="plan-ntnu"
ENV_FILE="/etc/plan/env"
DO_RECREATE=0
CHECK_ONLY=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --image)
      IMAGE_REF="$2"
      shift 2
      ;;
    --unit)
      UNIT_NAME="$2"
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
    --recreate)
      DO_RECREATE=1
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

revert_image_ref() {
  local image_name="$1"
  local image_id="$2"
  if [[ "$image_name" == *@* ]]; then
    printf '%s\n' "$image_name"
  else
    printf '%s@%s\n' "${image_name%%:*}" "$image_id"
  fi
}

if ! sudo podman container exists "$CONTAINER_NAME"; then
  echo "Container does not exist: $CONTAINER_NAME" >&2
  exit 1
fi

before_name="$(sudo podman inspect "$CONTAINER_NAME" --format '{{.ImageName}}')"
before_id="$(sudo podman inspect "$CONTAINER_NAME" --format '{{.Image}}')"
revert_ref="$(revert_image_ref "$before_name" "$before_id")"

log "Current runtime image"
echo "ImageName: $before_name"
echo "ImageID:   $before_id"
echo "Rollback (restart mode): $0 --image $revert_ref"
echo "Rollback (recreate mode): $0 --recreate --image $revert_ref"

log "Pull image"
sudo podman pull "$IMAGE_REF"

target_id="$(sudo podman image inspect "$IMAGE_REF" --format '{{.Id}}')"
log "Pulled target image"
echo "TargetRef: $IMAGE_REF"
echo "TargetID:  $target_id"

if [ "$CHECK_ONLY" -eq 1 ]; then
  if [ "$before_id" = "$target_id" ]; then
    echo "Status: up to date"
    exit 0
  else
    echo "Status: runtime differs from pulled target"
    exit 1
  fi
fi

if [ "$DO_RECREATE" -eq 0 ]; then
  log "Restart unit (default mode; no recreate)"
  sudo systemctl restart "$UNIT_NAME"
  sudo systemctl is-active --quiet "$UNIT_NAME"
else
  log "Recreate container + regenerate unit"
  sudo systemctl stop "$UNIT_NAME" || true
  sudo podman rm -f "$CONTAINER_NAME" || true

  sudo podman create \
    --name "$CONTAINER_NAME" \
    --network host \
    --user 33:33 \
    --env-file "$ENV_FILE" \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777 \
    --cap-drop=ALL \
    --security-opt no-new-privileges \
    -v /var/lib/plan:/var/lib/plan:rw,nosuid,nodev,noexec \
    -v /run/plan:/run/uwsgi:rw,nosuid,nodev,noexec \
    "$IMAGE_REF"

  sudo podman generate systemd --name "$CONTAINER_NAME" --files --new
  sudo install -D -m 0644 "container-${CONTAINER_NAME}.service" "/etc/systemd/system/${UNIT_NAME}"
  sudo systemctl daemon-reload
  sudo systemctl enable --now "$UNIT_NAME"
fi

after_name="$(sudo podman inspect "$CONTAINER_NAME" --format '{{.ImageName}}')"
after_id="$(sudo podman inspect "$CONTAINER_NAME" --format '{{.Image}}')"

log "Runtime image after action"
echo "ImageName: $after_name"
echo "ImageID:   $after_id"

if [ "$after_id" = "$target_id" ]; then
  echo "Result: runtime matches target"
else
  echo "Result: runtime does not match target" >&2
  echo "Rollback (restart mode): $0 --image $revert_ref" >&2
  echo "Rollback (recreate mode): $0 --recreate --image $revert_ref" >&2
  if [ "$DO_RECREATE" -eq 0 ]; then
    echo "Hint: retry with --recreate" >&2
  fi
  exit 1
fi

log "Revert command"
echo "$0 --recreate --image $revert_ref"

log "Recent logs"
sudo podman logs --tail 50 "$CONTAINER_NAME" || true
