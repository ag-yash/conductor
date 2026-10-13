# One small image serves both the API and the standalone worker. Compose chooses
# the command, while this image preserves the same Python package for both.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system conductor && useradd --system --gid conductor --create-home conductor

COPY pyproject.toml README.md LICENSE ./
COPY backend ./backend
COPY examples ./examples

RUN pip install . && mkdir /data && chown -R conductor:conductor /app /data

USER conductor

EXPOSE 8080

CMD ["conductor-api"]
