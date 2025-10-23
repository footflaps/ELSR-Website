#!/usr/bin/env bash
#
# Populates Docker named volumes for static, uploads, and config content.
# Usage: ./scripts/fill_site_volumes.sh
#

set -euo pipefail

CYAN=$(printf '\033[0;36m')
GREEN=$(printf '\033[0;32m')
YELLOW=$(printf '\033[1;33m')
NC=$(printf '\033[0m')

FLASK_CONTAINER="elsr-web"

LOCAL_STATIC="./file_mounts/static"
LOCAL_UPLOADS="./file_mounts/user_uploads"
LOCAL_CONFIG="./file_mounts/config"

echo -e "${CYAN}🚀 Populating Docker volumes...${NC}"

copy_to_container() {
  local SRC=$1
  local DEST_CONTAINER=$2
  local DEST_PATH=$3

  if [ -d "$SRC" ]; then
    echo -e "${CYAN}→ Copying $(basename "$SRC") into ${DEST_CONTAINER}:${DEST_PATH}${NC}"
    docker cp "${SRC}/." "${DEST_CONTAINER}:${DEST_PATH}/"
  else
    echo -e "${YELLOW}⚠️  Skipped: ${SRC} not found${NC}"
  fi
}

# --- Static ---
copy_to_container "$LOCAL_STATIC" "$FLASK_CONTAINER" "/app/static"

# --- Uploads ---
copy_to_container "$LOCAL_UPLOADS" "$FLASK_CONTAINER" "/app/user_uploads"

# --- Web Config ---
copy_to_container "$LOCAL_CONFIG" "$FLASK_CONTAINER" "/app/config"


echo -e "${GREEN}✅ Volumes populated successfully.${NC}"


# -------------------------------------------------------------------------------------------------------------- #
# Fix ownership and permissions inside Flask container
# -------------------------------------------------------------------------------------------------------------- #
echo -e "${CYAN}🔧 Fixing ownership for elsr user...${NC}"

docker exec -u root "${FLASK_CONTAINER}" bash -c "
  chown -R elsr:elsr /app/config /app/user_uploads /app/static 2>/dev/null || true
  chmod -R u+rwX,go+rX /app/config /app/user_uploads /app/static 2>/dev/null || true
"

echo -e "${GREEN}✅ Permissions corrected for user 'elsr'.${NC}"
