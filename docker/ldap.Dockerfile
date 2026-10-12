FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends slapd ldap-utils ca-certificates && rm -rf /var/lib/apt/lists/*
COPY scripts/ldap-start.sh /usr/local/bin/platform-ldap
ENTRYPOINT ["bash", "/usr/local/bin/platform-ldap"]
