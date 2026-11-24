FROM python:3.13.18-slim-bookworm@sha256:c3f3ace1c09d3d90cb79b17c6a1037282e82df75a8870929b2cbc667ddb7898e AS base
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

FROM base AS builder
RUN pip install --no-cache-dir uv==0.13.9
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM base AS runtime
COPY --from=builder /app/.venv /app/.venv
COPY filmoteka filmoteka
COPY manage.py .
USER 10001
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "filmoteka.wsgi"]

FROM builder AS test
RUN uv sync --frozen && PLAYWRIGHT_BROWSERS_PATH=/opt/browsers playwright install --with-deps chromium
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/browsers
COPY . .
USER 10001
