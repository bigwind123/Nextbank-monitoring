set -euo pipefail
cd /runtime/certs
if [ ! -f ca/ca.crt ]; then
    elasticsearch-certutil ca --silent --pem --out ca.zip
    unzip -q ca.zip
    rm ca.zip
fi
if [ ! -f nginx/nginx.crt ]; then
    elasticsearch-certutil cert --silent --pem --in /runtime/instances.yml --ca-cert ca/ca.crt --ca-key ca/ca.key --out nodes.zip
    unzip -qo nodes.zip
    rm nodes.zip
fi
chown -R 1000:0 /runtime/certs
find /runtime/certs -type d -exec chmod 755 {} \;
find /runtime/certs -name '*.crt' -exec chmod 644 {} \;
find /runtime/certs -name '*.key' -exec chmod 640 {} \;
chown root:root /runtime/certs/ca/ca.key
chmod 600 /runtime/certs/ca/ca.key
chgrp -R 0 /runtime
chmod 755 /runtime
chmod 770 /runtime/secrets
find /runtime/secrets -type f -exec chmod 640 {} \;
chmod 640 /runtime/platform.json /runtime/ldap.conf /runtime/directory.ldif
