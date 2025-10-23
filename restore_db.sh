#!/usr/bin/env bash
#
# Usage:
#   ./restore_db.sh /absolute/path/to/elsr_schema_backup.dump
#
# Restores a PostgreSQL dump file into the elsr_postgres Docker container.
# Works for custom (-F c) or plain SQL dumps.
#


# -------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------- #
RED='\033[0;31m'
YELLOW='\033[0;93m'
CYAN='\033[0;36m'
CLEAR='\033[0m'
# Where we look for the ENV file to get credentials
ENV_FILE="./run_docker.env"
# Tmp path in PostgreSQL container for copying in file
TMP_PATH="/tmp/elsr_restore_input"
CONTAINER_NAME="elsr-postgres"


# -------------------------------------------------------------------------------------------------------------- #
# Display usage
# -------------------------------------------------------------------------------------------------------------- #
if [ $# -ne 1 ] || [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
  echo
  echo "    Restores a PostgreSQL dump into the running elsr_postgres container."
  echo
  echo "    -- Usage: $0 /absolute/path/to/backup.dump"
  echo
  exit 1
fi


# -------------------------------------------------------------------------------------------------------------- #
# Header
# -------------------------------------------------------------------------------------------------------------- #
echo
echo "Restoring PostgreSQL file into Docker container..."


# -------------------------------------------------------------------------------------------------------------- #
# Validate inputs
# -------------------------------------------------------------------------------------------------------------- #
BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo -e "-- ${RED}ERROR${CLEAR}: File not found: $BACKUP_FILE"
  exit 1
fi

if [[ "$BACKUP_FILE" != /* ]]; then
  echo "-- ${RED}ERROR${CLEAR}: Please provide an absolute path."
  exit 1
fi


# -------------------------------------------------------------------------------------------------------------- #
# 1. Load environment variables (same as docker-compose)
# -------------------------------------------------------------------------------------------------------------- #
echo
echo -e "1. Looking for ENV File '${CYAN}${ENV_FILE}${CLEAR}'..."
if [ ! -f "$ENV_FILE" ]; then
  echo "-- ${RED}ERROR${CLEAR}: Environment file not found: ${ENV_FILE}"
  exit 1
else
  echo "-- File found!"
fi

# Export all non-commented vars
export $(grep -v '^#' "$ENV_FILE" | xargs)

# Expect these to be defined in run_docker.env:
#   POSTGRES_USER
#   POSTGRES_PASSWORD
#   POSTGRES_DB
DB_USER="${POSTGRES_USER}"
DB_NAME="${POSTGRES_DB}"
DB_PASSWORD="${POSTGRES_PASSWORD}"

# Double check
if [ -z "$DB_PASSWORD" ] || [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
  echo "-- ${RED}ERROR${CLEAR}: One of more DB params not set in env file."
  exit 1
else
  echo "-- POSTGRES_PASSWORD is set"
fi


# -------------------------------------------------------------------------------------------------------------- #
# 2. Need a container
# -------------------------------------------------------------------------------------------------------------- #
echo
echo -e "2. Looking for container '${CYAN}${CONTAINER_NAME}${CLEAR}'..."
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "-- ${RED}ERROR${CLEAR}: Container '${CONTAINER_NAME}' not running."
  exit 1
else
  echo "-- Found it!"
fi


# -------------------------------------------------------------------------------------------------------------- #
# 3. Copy file into container
# -------------------------------------------------------------------------------------------------------------- #
echo
echo -e "3. Copying backup file '${CYAN}${BACKUP_FILE}${CLEAR}' into container '${CYAN}${CONTAINER_NAME}${CLEAR}'..."
echo -e "${CYAN}"
docker cp "$BACKUP_FILE" "${CONTAINER_NAME}:${TMP_PATH}"
echo -e "${CLEAR}"


# -------------------------------------------------------------------------------------------------------------- #
# 4. Check for existing schema and confirm deletion
# -------------------------------------------------------------------------------------------------------------- #
echo
echo "4. Checking for existing schema..."
if docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -tAc "SELECT 1 FROM information_schema.schemata WHERE schema_name='elsr';" | grep -q 1; then
  echo
  echo -e "-- ${YELLOW}WARNING${CLEAR}: Schema '${CYAN}elsr${CLEAR}' already exists in '${CYAN}${DB_NAME}${CLEAR}'."
  echo -e "-- This action will permanently delete all data in that schema."
  echo
  echo -ne "Type '${RED}DELETE${CLEAR}' to confirm and continue:"
  read -p "" confirm
  if [ "$confirm" != "DELETE" ]; then
    echo
    echo "-- Aborted — schema not dropped."
    echo
    exit 1
  fi
  echo "-- Dropping existing schema..."
  echo -e "${CYAN}"
  docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -c "DROP SCHEMA IF EXISTS elsr CASCADE;" 2>&1 | sed "s/^/-- /;" || true
  docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -c "CREATE SCHEMA elsr AUTHORIZATION ${DB_USER};" 2>&1 | sed "s/^/-- /;" || true
  echo -e "${CLEAR}"

else
  echo "-- Schema 'elsr' not found — proceeding with restore."
fi


# -------------------------------------------------------------------------------------------------------------- #
# 5. Restore PostgreSQL
# -------------------------------------------------------------------------------------------------------------- #
echo
echo "5. Restoring database..."
# Run pg_restore (or psql) and pipe its stdout+stderr through sed to colourise
echo -e "${CYAN}"

docker exec -e PGPASSWORD="$DB_PASSWORD" -i "$CONTAINER_NAME" \
       pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --verbose "$TMP_PATH" 2>&1 | sed "s/^/-- /;"

echo -e "${CLEAR}"


# -------------------------------------------------------------------------------------------------------------- #
# 6. Cleanup
# -------------------------------------------------------------------------------------------------------------- #
echo
echo "6. Cleaning up temporary file..."
echo -e "${CYAN}"
docker exec "${CONTAINER_NAME}" rm -f "${TMP_PATH}"
echo -e "${CLEAR}"


# -------------------------------------------------------------------------------------------------------------- #
# Done!
# -------------------------------------------------------------------------------------------------------------- #
echo
echo "8. Restore complete!"
echo -e "-- Container ${CYAN}${CONTAINER_NAME}${CLEAR} updated with:"
echo -e "---- DB_NAME = '${CYAN}${DB_NAME}${CLEAR}'"
echo -e "---- DB_USER = '${CYAN}${DB_USER}${CLEAR}'"
echo -e "---- DB_PASSWORD = '${CYAN}${DB_PASSWORD}${CLEAR}'"
echo
