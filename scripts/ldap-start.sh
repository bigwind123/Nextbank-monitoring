set -euo pipefail
if [ ! -f /var/lib/ldap/DB_CONFIG_PLATFORM ]; then
    cp /runtime/ldap.conf /etc/ldap/slapd-platform.conf
    slapadd -f /etc/ldap/slapd-platform.conf -l /runtime/directory.ldif
    touch /var/lib/ldap/DB_CONFIG_PLATFORM
    chown -R openldap:openldap /var/lib/ldap
fi
exec slapd -f /runtime/ldap.conf -h "${LDAP_LISTEN}" -d 0 -u openldap -g root
