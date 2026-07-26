#!/bin/sh
set -eu

REPO_URL="https://github.com/Haoran-98/Your_AI_Postgraduate.git"
INSTALL_ROOT="${YAP_INSTALL_ROOT:-$HOME/.local/share/Your_AI_Postgraduate}"
CODEX_SKILLS="${CODEX_HOME:-$HOME/.codex}/skills"
SOURCE=""
MODE="link"
UPDATE=0

usage() {
  cat <<'EOF'
Install the complete Your AI Postgraduate Skill suite.

Usage: sh install.sh [options]
  --source DIR       Install from an existing checkout or extracted bundle.
  --install-root DIR Clone location used when no local source is available.
  --skills-dir DIR   Codex skills directory. Default: $CODEX_HOME/skills.
  --copy             Copy Skill directories instead of linking them.
  --update           Fast-forward an existing clean cloned installation.
  --help             Show this help.

Existing non-managed Skill directories are never overwritten.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --source)
      SOURCE=$2
      shift 2
      ;;
    --install-root)
      INSTALL_ROOT=$2
      shift 2
      ;;
    --skills-dir)
      CODEX_SKILLS=$2
      shift 2
      ;;
    --copy)
      MODE="copy"
      shift
      ;;
    --update)
      UPDATE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$SOURCE" ]; then
  SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)
  if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/skills/your-ai-postgraduate/SKILL.md" ]; then
    SOURCE=$SCRIPT_DIR
  elif [ -f "$INSTALL_ROOT/skills/your-ai-postgraduate/SKILL.md" ]; then
    SOURCE=$INSTALL_ROOT
  else
    command -v git >/dev/null 2>&1 || {
      echo "git is required when installing without a downloaded bundle." >&2
      exit 1
    }
    if [ -e "$INSTALL_ROOT" ]; then
      echo "Install root exists but is not a valid Your AI Postgraduate checkout: $INSTALL_ROOT" >&2
      exit 1
    fi
    mkdir -p "$(dirname -- "$INSTALL_ROOT")"
    git clone --depth 1 "$REPO_URL" "$INSTALL_ROOT"
    SOURCE=$INSTALL_ROOT
  fi
fi

SOURCE=$(CDPATH= cd -- "$SOURCE" && pwd)
if [ ! -f "$SOURCE/skills/your-ai-postgraduate/SKILL.md" ]; then
  echo "Invalid source; missing skills/your-ai-postgraduate/SKILL.md: $SOURCE" >&2
  exit 1
fi

if [ "$UPDATE" -eq 1 ] && [ -d "$SOURCE/.git" ]; then
  if ! git -C "$SOURCE" diff --quiet || ! git -C "$SOURCE" diff --cached --quiet; then
    echo "Refusing to update a checkout with local changes: $SOURCE" >&2
    exit 1
  fi
  git -C "$SOURCE" pull --ff-only
fi

mkdir -p "$CODEX_SKILLS"
conflicts=0
installed=0
for skill_dir in "$SOURCE"/skills/*; do
  [ -d "$skill_dir" ] || continue
  skill_name=$(basename -- "$skill_dir")
  destination="$CODEX_SKILLS/$skill_name"
  if [ -L "$destination" ]; then
    current=$(readlink "$destination")
    if [ "$current" = "$skill_dir" ]; then
      installed=$((installed + 1))
      continue
    fi
    echo "Conflict: $destination is a link to $current" >&2
    conflicts=$((conflicts + 1))
    continue
  fi
  if [ -e "$destination" ]; then
    echo "Conflict: $destination already exists and was not changed" >&2
    conflicts=$((conflicts + 1))
    continue
  fi
  if [ "$MODE" = "copy" ]; then
    cp -R "$skill_dir" "$destination"
  else
    ln -s "$skill_dir" "$destination"
  fi
  installed=$((installed + 1))
done

if [ "$conflicts" -gt 0 ]; then
  echo "Installed or retained $installed Skills; $conflicts conflicts require manual review." >&2
  exit 2
fi

printf '%s\n' "Installed $installed Skills from $SOURCE"
printf '%s\n' "Codex skills directory: $CODEX_SKILLS"
printf '%s\n' "Set YOUR_AI_POSTGRADUATE_HOME=$SOURCE when running repository scripts."
