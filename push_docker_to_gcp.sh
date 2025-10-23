#!/usr/bin/env bash
# -------------------------------------------------------------------------------- #
# Summary
# -------------------------------------------------------------------------------- #
#
# We deploy the site in production by pulling the ELSR Flask Docker image
# from GCP Artifacts Registry. To make it super simple to know which version we're
# on and which is deployed, we use a tag of from "v<X>" where X just increments. The
# Artifacts Registry is configured for immutable tags, so we can't over write an
# existing tag by accident.
#
# -------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------- #
CYAN=$(printf '\033[0;36m')
NC=$(printf '\033[0m')


# -------------------------------------------------------------------------------- #
# Header
# -------------------------------------------------------------------------------- #
echo
echo "Pushing latest docker image to GCP Artifacts Registry..."
echo


# -------------------------------------------------------------------------------- #
# Config
# -------------------------------------------------------------------------------- #
REGION="europe-west2"
PROJECT_ID="elsr-website"
REPO="elsr-docker-images"
IMAGE_NAME="elsr-web"
REMOTE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}"

set -euo pipefail


# -------------------------------------------------------------------------------- #
# 1. Find latest tag number (start at v0 if none exist)
# -------------------------------------------------------------------------------- #
echo "1. Checking existing tags..."
echo "-- REMOTE_PATH = '${REMOTE_PATH}'"
TAGS="$(gcloud artifacts docker images list "${REMOTE_PATH}" --include-tags --format="value(TAGS)" | sed '/^[[:space:]]*$/d')"
echo -e "-- Tags = '${CYAN}${TAGS}${NC}'"

LATEST_TAG_NUM=$(echo "${TAGS}" | tr ',' '\n' | grep -E '^v[0-9]+$' | sed 's/v//' | sort -n | tail -1 || echo "")

if [ -z "${LATEST_TAG_NUM}" ]; then
  echo "-- No existing images found. Starting fresh at v0."
  LATEST_TAG_NUM=-1
fi

LAST_TAG="v${LATEST_TAG_NUM}"
NEXT_TAG="v$((LATEST_TAG_NUM + 1))"

echo "-- Latest existing tag: ${LAST_TAG}"
echo "-- Next tag to use:     ${NEXT_TAG}"
echo


# -------------------------------------------------------------------------------- #
# 2. Check for local image
# -------------------------------------------------------------------------------- #
echo -e "2. Checking for local image '${CYAN}${IMAGE_NAME}${NC}'..."
echo -e "${CYAN}"
if ! docker images | grep "${IMAGE_NAME}"; then
  echo -e "${NC}"
  echo "-- No local image named '${IMAGE_NAME}' found."
  echo "-- Build it first using: docker compose build"
  exit 1
else
  echo -e "${NC}"
  echo -e "-- Found image '${CYAN}${IMAGE_NAME}${NC}'"
fi


# -------------------------------------------------------------------------------- #
# 3. Verify uniqueness (compare image digests)
# -------------------------------------------------------------------------------- #
echo
echo "3. Checking image uniqueness..."

LOCAL_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "${IMAGE_NAME}:latest" 2>/dev/null | cut -d'@' -f2 || true)
REMOTE_DIGEST=$(gcloud artifacts docker images describe "${REMOTE_PATH}:${LAST_TAG}" --format="value(image_summary.digest)" 2>/dev/null || echo "")
echo -e "-- LOCAL_DIGEST = '${CYAN}${LOCAL_DIGEST}${NC}"
echo -e "-- REMOTE_DIGEST = '${CYAN}${REMOTE_DIGEST}${NC}"

if [ -n "${LOCAL_DIGEST}" ] && [ -n "${REMOTE_DIGEST}" ]; then

  if [ "${LOCAL_DIGEST}" = "${REMOTE_DIGEST}" ]; then
    echo "-- The local image is identical to the latest pushed version (digest: ${LOCAL_DIGEST})"
    echo
    exit 1
  else
    echo "-- Image digest differs from last pushed version → proceeding."
  fi

else
  echo "-- No remote digest found (first push or missing metadata) → proceeding."
fi


# -------------------------------------------------------------------------------- #
# 4. Tag image
# -------------------------------------------------------------------------------- #
echo
echo "4. Tagging local image..."
FULL_TAG="${REMOTE_PATH}:${NEXT_TAG}"

echo "-- Tagging local image → ${FULL_TAG}"
docker tag "${IMAGE_NAME}:latest" "${FULL_TAG}"


# -------------------------------------------------------------------------------- #
# 5. Authenticate with GCP
# -------------------------------------------------------------------------------- #
echo
echo "5. Authenticating to GCP..."
echo -ne "${CYAN}"
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet 2>&1
echo -ne "${NC}"


# -------------------------------------------------------------------------------- #
# 6. Upload image
# -------------------------------------------------------------------------------- #
echo
echo "6. Pushing ${FULL_TAG}..."
echo -ne "${CYAN}"
docker push "${FULL_TAG}"
echo -ne "${NC}"


# -------------------------------------------------------------------------------- #
# 7. Done
# -------------------------------------------------------------------------------- #
echo
echo "7. Successfully pushed unique image"
echo "-- Tagged as ${NEXT_TAG}"
echo
