#!/usr/bin/env bash
# Pull-based deploy on the home server (docs/self-host.md): for each environment of compose.server.yaml,
# pull its images and start whatever changed, then remove dangling images.
#
#   scripts/server-pull.sh /home/asc/env/prod.env /home/asc/env/dev.env
#
# asc-pull.timer runs it every 5 minutes (ops/systemd/); its output goes to the journal:
#   journalctl -u asc-pull.service
# An environment that fails to pull or to become healthy does not stop the others, but the script then
# exits non-zero, so the run shows as failed in `systemctl status asc-pull.service`.
#
# Settings (environment variables, all optional):
#   ASC_COMPOSE_FILE   the compose file (default: compose.server.yaml next to this script's directory)
#   ASC_WAIT_TIMEOUT   seconds to wait for an environment to become healthy (default: 180)
set -uo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
compose_file=${ASC_COMPOSE_FILE:-$repo_dir/compose.server.yaml}
wait_timeout=${ASC_WAIT_TIMEOUT:-180}

log() {
  printf '%s\n' "$*"
}

compose() {
  local env_file=$1
  shift
  docker compose -f "$compose_file" --env-file "$env_file" "$@"
}

# The running backend container of an environment, empty if there is none.
backend_container() {
  compose "$1" ps -q backend 2>/dev/null
}

# APP_VERSION baked into the image of a container (sha-<7 hex>), or the short image ID for an image built
# without it. Read from the image, not the container, so the container's secrets never reach the journal.
image_version() {
  local image id version
  image=$(docker inspect -f '{{.Image}}' "$1" 2>/dev/null) || return 0
  id=${image#sha256:}
  version=$(docker image inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$image" 2>/dev/null |
    sed -n 's/^APP_VERSION=//p')
  printf '%s\n' "${version:-image ${id:0:12}}"
}

update_environment() {
  local env_file=$1 name before after
  name=$(basename -- "$env_file" .env)
  if [[ ! -r $env_file ]]; then
    log "$name: cannot read $env_file"
    return 1
  fi
  before=$(backend_container "$env_file")
  if ! compose "$env_file" pull --quiet; then
    log "$name: pull failed"
    return 1
  fi
  if ! compose "$env_file" up -d --wait --wait-timeout "$wait_timeout"; then
    log "$name: not healthy after ${wait_timeout}s, see: docker compose -p <project> logs backend"
    return 1
  fi
  after=$(backend_container "$env_file")
  if [[ $before == "$after" ]]; then
    log "$name: up to date"
  else
    log "$name: started $(image_version "$after")"
  fi
}

prune_images() {
  local output
  output=$(docker image prune -f) || return 1
  if grep -q '^Deleted' <<<"$output"; then
    log "$output"
  fi
}

main() {
  if [[ $# -eq 0 ]]; then
    log "usage: $0 ENV_FILE [ENV_FILE...]"
    return 2
  fi
  if [[ ! -r $compose_file ]]; then
    log "cannot read $compose_file"
    return 1
  fi
  local status=0 env_file
  for env_file in "$@"; do
    update_environment "$env_file" || status=1
  done
  prune_images || status=1
  return "$status"
}

main "$@"
