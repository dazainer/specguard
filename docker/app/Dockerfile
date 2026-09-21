FROM docker:27.5.1-cli AS dockercli
FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY backend/app app
COPY backend/evaluation-alembic.ini .
COPY backend/evaluation_migrations evaluation_migrations
COPY benchmarks /app/benchmarks
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
