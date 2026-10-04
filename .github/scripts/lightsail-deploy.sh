#!/usr/bin/env bash
# Deploy one image to a Lightsail container service and wait until it serves traffic.
#
# Required environment: SERVICE, IMAGE, ENV_TAG, DATABASE_URL, JWT_SECRET, CORS_ORIGINS,
# plus AWS credentials and AWS_REGION. Optional: CREATE_IF_MISSING=true (dev is ephemeral;
# the service is created with the tag env=$ENV_TAG, which the deploy role requires).
# Writes url=<service URL without the trailing slash> to $GITHUB_OUTPUT when it is set.
set -euo pipefail

: "${SERVICE:?}" "${IMAGE:?}" "${ENV_TAG:?}" "${DATABASE_URL:?}" "${JWT_SECRET:?}" "${CORS_ORIGINS:?}"
CREATE_IF_MISSING="${CREATE_IF_MISSING:-false}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-900}"
deadline=$((SECONDS + TIMEOUT_SECONDS))

service_field() {
  aws lightsail get-container-services --service-name "$SERVICE" \
    --query "containerServices[0].$1" --output text
}

wait_for_service() {
  local state
  while true; do
    state=$(service_field state)
    case "$state" in
      READY | RUNNING) return 0 ;;
      PENDING | DEPLOYING | UPDATING) ;;
      *) echo "Service $SERVICE is in state $state" >&2; return 1 ;;
    esac
    if ((SECONDS > deadline)); then echo "Timed out waiting for $SERVICE (state $state)" >&2; return 1; fi
    sleep 10
  done
}

if ! aws lightsail get-container-services --service-name "$SERVICE" > /dev/null 2> "$RUNNER_TEMP/lookup.err"; then
  if ! grep -q NotFoundException "$RUNNER_TEMP/lookup.err"; then cat "$RUNNER_TEMP/lookup.err" >&2; exit 1; fi
  if [[ "$CREATE_IF_MISSING" != "true" ]]; then
    echo "Container service $SERVICE does not exist" >&2
    exit 1
  fi
  echo "Creating container service $SERVICE (nano, scale 1, env=$ENV_TAG)"
  aws lightsail create-container-service --service-name "$SERVICE" --power nano --scale 1 \
    --tags "key=env,value=$ENV_TAG" > /dev/null
fi
wait_for_service

# Built from environment variables so that secrets never appear in the command line or logs.
containers="$RUNNER_TEMP/containers.json"
jq -n --arg image "$IMAGE" --arg db "$DATABASE_URL" --arg jwt "$JWT_SECRET" --arg cors "$CORS_ORIGINS" '{
  backend: {
    image: $image,
    ports: {"8000": "HTTP"},
    environment: {
      DATABASE_URL: $db, JWT_SECRET: $jwt, CORS_ORIGINS: $cors,
      ANALYZER: "stub", SEED_DEMO_DATA: "false"
    }
  }
}' > "$containers"
endpoint='{"containerName":"backend","containerPort":8000,"healthCheck":{"path":"/health","successCodes":"200","intervalSeconds":10,"timeoutSeconds":5,"healthyThreshold":2,"unhealthyThreshold":3}}'

version=$(aws lightsail create-container-service-deployment --service-name "$SERVICE" \
  --containers "file://$containers" --public-endpoint "$endpoint" \
  --query 'containerService.nextDeployment.version' --output text)
rm -f "$containers"
echo "Created deployment $version of $IMAGE"

while true; do
  state=$(aws lightsail get-container-service-deployments --service-name "$SERVICE" \
    --query "deployments[?version==\`$version\`].state | [0]" --output text)
  case "$state" in
    ACTIVE) break ;;
    FAILED) echo "Deployment $version failed; check: aws lightsail get-container-log --service-name $SERVICE --container-name backend" >&2; exit 1 ;;
  esac
  if ((SECONDS > deadline)); then echo "Timed out waiting for deployment $version (state $state)" >&2; exit 1; fi
  sleep 10
done
wait_for_service

url=$(service_field url)
url="${url%/}"
echo "Deployment $version is active at $url"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then echo "url=$url" >> "$GITHUB_OUTPUT"; fi
