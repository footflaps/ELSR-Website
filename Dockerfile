# -------------------------------------------------------------------------------- #
# Base Python runtime
# -------------------------------------------------------------------------------- #
FROM python:3.11-slim-bookworm AS base

# Stop pyc for smaller container
ENV PYTHONDONTWRITEBYTECODE=1
# Output immediately to docker logs
ENV PYTHONUNBUFFERED=1
# Smaller image
ENV PIP_NO_CACHE_DIR=1


# -------------------------------------------------------------------------------- #
# Builder stage to install dependencies without dev tools
# -------------------------------------------------------------------------------- #
FROM base AS builder
WORKDIR /app

# Copy requirements and install dependencies into /install
COPY requirements.txt ./
RUN pip install --prefix=/install -r requirements.txt


# -------------------------------------------------------------------------------- #
# Final runtime image
# -------------------------------------------------------------------------------- #
FROM base
WORKDIR /app


# -------------------------------------------------------------------------------- #
# Install curl for healthchecks
# -------------------------------------------------------------------------------- #
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*


# -------------------------------------------------------------------------------- #
# Create non-root user 'elsr' with no shell
# -------------------------------------------------------------------------------- #
RUN groupadd -r elsr && \
    useradd -r -g elsr -s /usr/sbin/nologin elsr


# -------------------------------------------------------------------------------- #
# Copy installed packages + app source
# -------------------------------------------------------------------------------- #
COPY --from=builder /install /usr/local
COPY ./core ./core
COPY gunicorn.conf.py /app/gunicorn.conf.py


# -------------------------------------------------------------------------------- #
# Create expected mount points for Docker volumes
# -------------------------------------------------------------------------------- #
RUN mkdir -p /app/static /app/user_uploads /app/config

# Create log directories locally
RUN mkdir -p /var/log/elsr && chown -R elsr:elsr /var/log/elsr


# -------------------------------------------------------------------------------- #
# Switch to non-root user
# -------------------------------------------------------------------------------- #
RUN chown -R elsr:elsr /app
USER elsr


# -------------------------------------------------------------------------------- #
# Expose app port (non-privileged)
# -------------------------------------------------------------------------------- #
EXPOSE 8000


# -------------------------------------------------------------------------------- #
# Run Gunicorn securely
# -------------------------------------------------------------------------------- #
CMD ["gunicorn",                                \
     "-b", "0.0.0.0:8000",                      \
     "--workers", "3",                          \
     "--threads", "2",                          \
     "-c", "/app/gunicorn.conf.py",             \
     "core.main:app"]
