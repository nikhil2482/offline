FROM python:3.13-slim AS build
WORKDIR /src
RUN python -m venv /venv
COPY requirements.lock .
RUN /venv/bin/pip install --no-cache-dir --require-hashes -r requirements.lock
COPY pyproject.toml README.md ./
COPY offline ./offline
RUN /venv/bin/pip install --no-cache-dir --no-deps . \
    && /venv/bin/pip uninstall --yes pip

FROM python:3.13-slim
# pip is not needed at runtime and its vendored libraries carry known CVEs.
RUN rm -rf /usr/local/lib/python3*/site-packages/pip /usr/local/lib/python3*/site-packages/pip-*.dist-info \
    /usr/local/lib/python3*/ensurepip /usr/local/bin/pip* \
    && apt-get update && apt-get upgrade --yes && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /venv /venv
WORKDIR /app
COPY sources.yaml .
COPY evals ./evals
ENV PATH=/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
HEALTHCHECK CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
CMD ["uvicorn", "offline.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
