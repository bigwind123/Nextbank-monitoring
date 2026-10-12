set -euo pipefail
export FLEET_ENROLL=1
export FLEET_URL="$(cat /runtime/fleet-base)"
export FLEET_CA=/runtime/certs/ca/ca.crt
export FLEET_ENROLLMENT_TOKEN="$(cat "${ENROLLMENT_FILE:-/runtime/secrets/agent-enrollment}")"
exec /usr/bin/elastic-agent container
