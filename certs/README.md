# Extra CA certificates

The Docker image trusts whatever `.crt` / `.pem` files you drop in this
directory. Use this on networks that intercept HTTPS (Netskope, Zscaler,
corporate SSL inspection). Without the intercept CA, `pip install` fails with:

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
self-signed certificate in certificate chain
```

These files stay local (see `.gitignore`). Do not commit tenant intercept CAs.

## Export from this Mac

```bash
python3 scripts/export_host_cas.py
docker compose up --build
```

That pulls the current `pypi.org` chain plus matching keychain CAs into this
folder.

## Manual

```bash
echo | openssl s_client -showcerts -connect pypi.org:443 -servername pypi.org
```

Save every issuer **except** the `CN=pypi.org` leaf as `certs/<name>.crt`.

## Without a CA file

```bash
PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org" \
  docker compose up --build
```
