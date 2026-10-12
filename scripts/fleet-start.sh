set -euo pipefail
export FLEET_SERVER_ENABLE=1
export FLEET_SERVER_ELASTICSEARCH_HOST="$(cat /runtime/es-base)"
export FLEET_SERVER_SERVICE_TOKEN="$(cat /runtime/secrets/fleet-service)"
export FLEET_SERVER_POLICY_ID=fleet-server-policy
export FLEET_SERVER_ES_CA=/runtime/certs/ca/ca.crt
export FLEET_SERVER_CERT=/runtime/certs/fleet/fleet.crt
export FLEET_SERVER_CERT_KEY=/runtime/certs/fleet/fleet.key
export FLEET_SERVER_PORT=8220
exec /usr/bin/elastic-agent container
