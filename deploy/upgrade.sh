#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage:
  $0 [options]

Options:
  --instance <name>    Instance name (default: ntnu)
  --image <ref>        Image ref to pull + set in quadlet (default: ghcr.io/adamcik/plan:latest)
  --unit <name>        systemd unit (default: plan-<instance>.service)
  --container <name>   container name (default: plan-<instance>)
  --quadlet-file <p>   Quadlet path (default: /etc/containers/systemd/<unit-base>.container)
  --image-override <p> Quadlet drop-in path for Image= override
                      (default: <quadlet-file>.d/image.conf)
  --extract-static     Extract static from pulled image before restart (default)
  --no-extract-static  Skip static extraction step
  --static-from <p>    Path inside image to extract (default: /var/lib/plan/static)
  --static-releases <p>
                      Host dir for versioned static releases
  --static-current <p>
                      Host symlink for active static release
  --check              Pull and compare only; do not modify quadlet or restart
  --dry-run            Print planned actions and exit
  -h, --help           Show this help

Examples:
  $0
  $0 --image ghcr.io/adamcik/plan@sha256:abcd...
  $0 --instance preprod --image ghcr.io/adamcik/plan:main
EOF
}

DEFAULT_INSTANCE_NAME="ntnu"
INSTANCE_NAME="$DEFAULT_INSTANCE_NAME"
IMAGE_REF="ghcr.io/adamcik/plan:latest"

UNIT_NAME=""
CONTAINER_NAME=""
QUADLET_FILE=""
IMAGE_OVERRIDE_FILE=""

LIB_DIR=""
RUN_DIR=""

EXTRACT_STATIC=1
STATIC_FROM="/var/lib/plan/static"
STATIC_RELEASES_DIR=""
STATIC_CURRENT_LINK=""

CHECK_ONLY=0
DRY_RUN=0

TARGET_DIGEST_REF=""
TARGET_OVERRIDE_REF=""

UNIT_SET=0
CONTAINER_SET=0
QUADLET_SET=0
IMAGE_OVERRIDE_SET=0
STATIC_RELEASES_SET=0
STATIC_CURRENT_SET=0

log() {
  printf '\n==> %s\n' "$*"
}

unit_to_quadlet_path() {
  local unit="$1"
  local base
  base="${unit%.service}"
  printf '/etc/containers/systemd/%s.container\n' "$base"
}

apply_instance_defaults() {
  LIB_DIR="/var/lib/plan/${INSTANCE_NAME}"
  RUN_DIR="/run/plan/${INSTANCE_NAME}"

  if [ "$CONTAINER_SET" -eq 0 ]; then
    CONTAINER_NAME="plan-${INSTANCE_NAME}"
  fi
  if [ "$UNIT_SET" -eq 0 ]; then
    UNIT_NAME="plan-${INSTANCE_NAME}.service"
  fi
  if [ "$QUADLET_SET" -eq 0 ]; then
    QUADLET_FILE="$(unit_to_quadlet_path "$UNIT_NAME")"
  fi
  if [ "$IMAGE_OVERRIDE_SET" -eq 0 ]; then
    IMAGE_OVERRIDE_FILE="${QUADLET_FILE}.d/image.conf"
  fi
  if [ "$STATIC_RELEASES_SET" -eq 0 ]; then
    STATIC_RELEASES_DIR="${LIB_DIR}/static/releases"
  fi
  if [ "$STATIC_CURRENT_SET" -eq 0 ]; then
    STATIC_CURRENT_LINK="${LIB_DIR}/static/current"
  fi
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
    --unit)
      UNIT_NAME="$2"
      UNIT_SET=1
      shift 2
      ;;
    --container)
      CONTAINER_NAME="$2"
      CONTAINER_SET=1
      shift 2
      ;;
    --quadlet-file)
      QUADLET_FILE="$2"
      QUADLET_SET=1
      shift 2
      ;;
    --image-override)
      IMAGE_OVERRIDE_FILE="$2"
      IMAGE_OVERRIDE_SET=1
      shift 2
      ;;
    --extract-static)
      EXTRACT_STATIC=1
      shift
      ;;
    --no-extract-static)
      EXTRACT_STATIC=0
      shift
      ;;
    --static-from)
      STATIC_FROM="$2"
      shift 2
      ;;
    --static-releases)
      STATIC_RELEASES_DIR="$2"
      STATIC_RELEASES_SET=1
      shift 2
      ;;
    --static-current)
      STATIC_CURRENT_LINK="$2"
      STATIC_CURRENT_SET=1
      shift 2
      ;;
    --check)
      CHECK_ONLY=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
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

log "Resolved configuration"
echo "Instance:    $INSTANCE_NAME"
echo "Container:   $CONTAINER_NAME"
echo "Unit:        $UNIT_NAME"
echo "QuadletFile: $QUADLET_FILE"
echo "ImageOvr:    $IMAGE_OVERRIDE_FILE"
echo "ImageRef:    $IMAGE_REF"
echo "LibDir:      $LIB_DIR"
echo "RunDir:      $RUN_DIR"
echo "StaticFrom:  $STATIC_FROM"
echo "StaticRel:   $STATIC_RELEASES_DIR"
echo "StaticCur:   $STATIC_CURRENT_LINK"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Dry run: no changes applied"
  exit 0
fi

if ! sudo test -f "$QUADLET_FILE"; then
  echo "Quadlet file not found: $QUADLET_FILE" >&2
  exit 1
fi

extract_static_release() {
  local image_ref="$1"
  local image_id="$2"
  local release_id
  release_id="${image_id#sha256:}"
  local release_dir="${STATIC_RELEASES_DIR}/${release_id}"
  local parent_dir
  parent_dir="$(dirname "$STATIC_CURRENT_LINK")"

  if sudo test -d "$release_dir"; then
    log "Static release already present"
    echo "ReleaseDir: $release_dir"
  else
    log "Extract static release from image"
    local ctr="plan-static-${release_id}"
    local tmp_dir="${release_dir}.tmp"

    sudo install -d -m 0755 "$STATIC_RELEASES_DIR"
    sudo rm -rf "$tmp_dir"
    sudo install -d -m 0755 "$tmp_dir"

    sudo podman rm -f "$ctr" >/dev/null 2>&1 || true
    sudo podman create --name "$ctr" "$image_ref" >/dev/null
    trap 'sudo podman rm -f "$ctr" >/dev/null 2>&1 || true' RETURN
    sudo podman cp "$ctr":"$STATIC_FROM"/. "$tmp_dir"/
    sudo podman rm -f "$ctr" >/dev/null
    trap - RETURN

    sudo mv "$tmp_dir" "$release_dir"
    echo "ReleaseDir: $release_dir"
  fi

  log "Atomically switch static current symlink"
  sudo install -d -m 0755 "$parent_dir"
  sudo ln -sfn "$release_dir" "${STATIC_CURRENT_LINK}.new"
  sudo mv -Tf "${STATIC_CURRENT_LINK}.new" "$STATIC_CURRENT_LINK"
  echo "CurrentLink: $STATIC_CURRENT_LINK -> $release_dir"
}

log "Current runtime image"
if sudo podman container exists "$CONTAINER_NAME"; then
  before_id="$(sudo podman inspect "$CONTAINER_NAME" --format '{{.Image}}')"
  before_name="$(sudo podman inspect "$CONTAINER_NAME" --format '{{.ImageName}}')"
  before_repo_digest="$(sudo podman image inspect "$before_name" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
  echo "Container: $CONTAINER_NAME"
  echo "ImageName:  $before_name"
  echo "ImageID:    $before_id"
  echo "RepoDigest: ${before_repo_digest:-<none>}"
else
  echo "Container not found: $CONTAINER_NAME"
  before_id=""
  before_name=""
  before_repo_digest=""
fi

log "Pull image"
sudo podman pull "$IMAGE_REF"
target_id="$(sudo podman image inspect "$IMAGE_REF" --format '{{.Id}}')"
TARGET_DIGEST_REF="$(sudo podman image inspect "$IMAGE_REF" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
if [ -n "$TARGET_DIGEST_REF" ]; then
  TARGET_OVERRIDE_REF="$TARGET_DIGEST_REF"
else
  TARGET_OVERRIDE_REF="$IMAGE_REF"
fi
echo "TargetRef: $IMAGE_REF"
echo "TargetID:  $target_id"
echo "TargetPin: $TARGET_OVERRIDE_REF"

if [ "$CHECK_ONLY" -eq 1 ]; then
  if [ -n "$before_id" ] && [ "$before_id" = "$target_id" ]; then
    echo "Status: up to date"
    exit 0
  fi
  echo "Status: runtime differs from pulled target"
  exit 1
fi

if [ "$EXTRACT_STATIC" -eq 1 ]; then
  extract_static_release "$IMAGE_REF" "$target_id"
fi

log "Write quadlet Image= drop-in override"
sudo install -d -m 0755 "$(dirname "$IMAGE_OVERRIDE_FILE")"
sudo tee "$IMAGE_OVERRIDE_FILE" >/dev/null <<EOF
# Managed by deploy/upgrade.sh
# Requested image: $IMAGE_REF
# To roll back, set Image=<previous-ref> and restart $UNIT_NAME.
# Previous runtime image: ${before_repo_digest:-${before_name:-<unknown>}}
[Container]
Image=$TARGET_OVERRIDE_REF # requested: $IMAGE_REF
EOF

log "Reload + restart service"
sudo systemctl daemon-reload
sudo systemctl restart "$UNIT_NAME"
sudo systemctl is-active --quiet "$UNIT_NAME"

after_id="$(sudo podman inspect "$CONTAINER_NAME" --format '{{.Image}}')"
after_name="$(sudo podman inspect "$CONTAINER_NAME" --format '{{.ImageName}}')"
log "Runtime image after action"
echo "ImageName: $after_name"
echo "ImageID:   $after_id"

if [ "$after_id" = "$target_id" ]; then
  echo "Result: runtime matches target"
else
  echo "Result: runtime does not match target" >&2
  echo "Hint: verify $QUADLET_FILE and unit $UNIT_NAME" >&2
  exit 1
fi

log "Recent logs"
sudo podman logs --tail 50 "$CONTAINER_NAME" || true
