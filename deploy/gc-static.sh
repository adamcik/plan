#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage:
  $0 [options]

Delete inactive static releases created by deploy/upgrade.sh.

Options:
  --instance <name>    Instance name (default: ntnu)
  --static-releases <p>
                       Host dir containing versioned static releases
  --static-current <p> Host symlink for the active static release
  --dry-run            Print releases that would be removed
  -h, --help           Show this help
EOF
}

INSTANCE_NAME="ntnu"
STATIC_RELEASES_DIR=""
STATIC_CURRENT_LINK=""
STATIC_RELEASES_SET=0
STATIC_CURRENT_SET=0
DRY_RUN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --instance)
      INSTANCE_NAME="$2"
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
      usage >&2
      exit 2
      ;;
  esac
done

LIB_DIR="/var/lib/plan/${INSTANCE_NAME}"
if [ "$STATIC_RELEASES_SET" -eq 0 ]; then
  STATIC_RELEASES_DIR="${LIB_DIR}/static/releases"
fi
if [ "$STATIC_CURRENT_SET" -eq 0 ]; then
  STATIC_CURRENT_LINK="${LIB_DIR}/static/current"
fi

if ! sudo test -d "$STATIC_RELEASES_DIR"; then
  echo "Static releases directory not found: $STATIC_RELEASES_DIR" >&2
  exit 1
fi
if ! sudo test -L "$STATIC_CURRENT_LINK"; then
  echo "Active static release is not a symlink: $STATIC_CURRENT_LINK" >&2
  exit 1
fi

releases_dir="$(sudo realpath -e "$STATIC_RELEASES_DIR")"
current_dir="$(sudo realpath -e "$STATIC_CURRENT_LINK")"
case "$current_dir" in
  "$releases_dir"/*) ;;
  *)
    echo "Active static release resolves outside releases directory: $current_dir" >&2
    exit 1
    ;;
esac

echo "Static releases: $releases_dir"
echo "Active release:  $current_dir"

while IFS= read -r -d '' release_dir; do
  if [ "$release_dir" = "$current_dir" ]; then
    continue
  fi

  release_name="${release_dir##*/}"
  # upgrade.sh names releases from the 64-character SHA-256 image ID.
  if [[ ! "$release_name" =~ ^[0-9a-f]{64}$ ]]; then
    continue
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "Would remove: $release_dir"
  else
    echo "Removing: $release_dir"
    sudo rm -rf -- "$release_dir"
  fi
done < <(sudo find "$releases_dir" -mindepth 1 -maxdepth 1 -type d -print0)
