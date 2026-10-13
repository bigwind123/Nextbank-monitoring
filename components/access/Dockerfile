FROM __CFG_1521__

WORKDIR /usr/src/app

RUN apk update
RUN apk add \
        libldap \
        gcc \
        libc-dev \
        python3-dev \
        openldap-dev
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY CM-python-ldap/nginx-ldap-auth-daemon.py  /usr/src/app/nginx-ldap-auth-daemon.py
CMD [ "python", "nginx-ldap-auth-daemon.py" ]
