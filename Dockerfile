FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home transit
USER transit
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn seoul_transit.app:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
