set -euo pipefail
cd /runtime/certs
if [ ! -f ca/ca.crt ]; then
    elasticsearch-certutil ca --silent --pem --out /runtime/certs/ca.zip
    unzip -q /runtime/certs/ca.zip -d /runtime/certs
    rm /runtime/certs/ca.zip
fi
if [ ! -f nginx/nginx.crt ]; then
    elasticsearch-certutil cert --silent --pem --in /runtime/instances.yml --ca-cert /runtime/certs/ca/ca.crt --ca-key /runtime/certs/ca/ca.key --out /runtime/certs/nodes.zip
    unzip -qo /runtime/certs/nodes.zip -d /runtime/certs
    rm /runtime/certs/nodes.zip
fi
chown -R 1000:0 /runtime/certs
find /runtime/certs -type d -exec chmod 755 {} \;
find /runtime/certs -name '*.crt' -exec chmod 644 {} \;
find /runtime/certs -name '*.key' -exec chmod 640 {} \;
chown root:root /runtime/certs/ca/ca.key
chmod 600 /runtime/certs/ca/ca.key
chgrp -R 0 /runtime
chmod 770 /runtime
chmod 770 /runtime/secrets
find /runtime/secrets -type f -exec chmod 640 {} \;
chmod 640 /runtime/platform.json /runtime/ldap.conf /runtime/directory.ldif
chmod 660 /runtime/master.yml
cp /runtime/secrets/elastic-password /runtime/secrets/es-bootstrap-password
chown 1000:0 /runtime/secrets/es-bootstrap-password
chmod 600 /runtime/secrets/es-bootstrap-password
