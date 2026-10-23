# syntax=docker/dockerfile:1

# Pin both images by digest before the first deploy (M8), e.g.
#   docker buildx imagetools inspect python:3.12-slim-bookworm
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5

FROM ${UV_IMAGE} AS uv

# Builder: resolve the locked dependencies into a virtual environment.
FROM ${PYTHON_IMAGE} AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/srv/.venv
WORKDIR /srv
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Runtime: no uv, no build tools, non root.
FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/.venv/bin:${PATH}" \
    GUNICORN_WORKERS=2

# unixODBC lets pyodbc import. Microsoft ODBC Driver 18 is needed to reach Azure SQL and Fabric.
RUN apt-get update \
    && apt-get install -y --no-install-recommends unixodbc \
    && rm -rf /var/lib/apt/lists/*

# Microsoft ODBC Driver 18: disabled until acceptance of the Microsoft EULA is authorised
# (see docs/open_questions.md). Verify these steps against Microsoft Learn before enabling.
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends curl gnupg \
#     && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
#        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
#     && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
#        -o /etc/apt/sources.list.d/mssql-release.list \
#     && apt-get update \
#     && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
#     && apt-get purge -y curl gnupg && apt-get autoremove -y \
#     && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /srv/app
COPY --from=builder /srv/.venv /srv/.venv
COPY config/ /srv/config/
COPY app/ ./
RUN python manage.py collectstatic --noinput

USER 10001
EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn fabric_ui.wsgi --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS} --access-logfile -"]
