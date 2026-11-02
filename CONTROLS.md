# Security control mapping

This system was designed with the controls below in mind. Control names follow NIST SP 800 53. The system has not been independently assessed. The list shows where each control is addressed in the code, so a reviewer can check it.

### AC 3 Access enforcement

Every route except health checks a bearer token and a role. See `offline/api.py`.

### AC 6 Least privilege

Analysts can ask questions. Only admins can read the audit log. Containers run as unprivileged users with all capabilities dropped. See `offline/auth.py` and `compose.yaml`.

### AC 7 Unsuccessful logon attempts

Failed token checks are logged with the client address, and each user is rate limited. See `offline/api.py` and `offline/ratelimit.py`.

### AU 2 and AU 3 Event logging and content

Questions, answers, ingests, user creation, failed logins and denied requests are logged with time, user, event and outcome. See `offline/audit.py`.

### AU 9 Protection of audit information

Audit entries are hash chained. The api refuses to start on a broken chain. See `offline/audit.py`.

### CM 2 Baseline configuration

Sources, model names and container images are pinned in version controlled files. See `sources.yaml`, `compose.yaml` and the Dockerfiles.

### IA 5 Authenticator management

Tokens are generated with a cryptographic random source, shown once, and stored only as hashes in a file with 0600 permissions. See `offline/auth.py`.

### RA 5 Vulnerability monitoring

pip audit, npm audit, Trivy and CodeQL run in CI, and Dependabot watches every ecosystem. See `.github`.

### SA 11 Developer testing

Unit tests cover the allowlist, hashing, parsing, citation checks, audit chain and API roles. Integration tests cover pgvector and network isolation. See `tests` and `.github/workflows/ci.yml`.

### SC 7 Boundary protection

The backend network is internal with no route out. Only the web container is published, on localhost only. CI checks that the api cannot reach the internet. See `compose.yaml` and `offline/egress_check.py`.

### SC 8 Transmission confidentiality

Sources are fetched over HTTPS only, and cloud mode uses HTTPS. Traffic inside the Docker network is plain HTTP. A production deployment would add TLS at the web container with a trusted certificate.

### SI 7 Software and information integrity

Source files are hash checked before ingest. Python dependencies are hash checked at install. See `offline/sources.py` and the Dockerfile.

### SI 10 Information input validation

Questions are length limited and extra fields are rejected. Source URLs, formats and markings are validated against the allowlist. See `offline/api.py` and `offline/sources.py`.

### SR 4 Provenance

Models come from U.S. companies, as listed in the README. Each image gets a CycloneDX SBOM in CI.
