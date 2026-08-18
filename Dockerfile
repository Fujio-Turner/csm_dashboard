FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends wget tar libicu76 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Optional extra CAs for TLS-inspecting networks (Netskope, Zscaler, …).
# Drop PEM/CRT files in ./certs/ — see certs/README.md.
COPY certs/ /usr/local/share/ca-certificates/
RUN update-ca-certificates

# pip/requests use certifi by default and ignore the system store unless told.
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt

# Escape hatch when you cannot install the intercept CA:
#   PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org" docker compose up --build
ARG PIP_TRUSTED_HOST=
ENV PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

COPY cblite_config.json /app/cblite_config.json
ARG CBLITE_VERSION=
ARG CBLITE_EDITION=

RUN set -eux; \
    CFG_VERSION="$(python -c 'import json; print(json.load(open("/app/cblite_config.json"))["version"])')"; \
    CFG_EDITION="$(python -c 'import json; print(json.load(open("/app/cblite_config.json"))["edition"])')"; \
    CFG_PLATFORM="$(python -c 'import json; print(json.load(open("/app/cblite_config.json")).get("platform","linux-x86_64"))')"; \
    VERSION="${CBLITE_VERSION:-$CFG_VERSION}"; \
    EDITION="${CBLITE_EDITION:-$CFG_EDITION}"; \
    echo "Installing libcblite ${VERSION} (${EDITION}) for ${CFG_PLATFORM}"; \
    wget -q "https://packages.couchbase.com/releases/couchbase-lite-c/${VERSION}/couchbase-lite-c-${EDITION}-${VERSION}-${CFG_PLATFORM}.tar.gz" \
        -O /tmp/cblite.tar.gz; \
    mkdir -p /opt/cblite; \
    tar -xzf /tmp/cblite.tar.gz -C /tmp; \
    cp -r /tmp/libcblite-${VERSION}/lib /opt/cblite/lib; \
    cp -r /tmp/libcblite-${VERSION}/include /opt/cblite/include; \
    rm -rf /tmp/cblite.tar.gz /tmp/libcblite-${VERSION}

ENV CBLITE_LIB_PATH=/opt/cblite/lib/x86_64-linux-gnu/libcblite.so
ENV LD_LIBRARY_PATH=/opt/cblite/lib/x86_64-linux-gnu:/opt/cblite/lib:${LD_LIBRARY_PATH}
ENV CSM_DASHBOARD_DB_PATH=/data/csm_dashboard.cblite2
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY schema /app/schema
COPY docs /app/docs
COPY guides /app/guides
COPY prompts /app/prompts
COPY fixtures /app/fixtures
COPY config.example.json /app/config.example.json
COPY cblite_config.json /app/cblite_config.json

RUN pip install --no-cache-dir -e .

EXPOSE 8788

CMD ["python", "-m", "csm_dashboard"]
