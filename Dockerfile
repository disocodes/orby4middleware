FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
RUN pip install --no-cache-dir .[postgres]
EXPOSE 8080
CMD ["uvicorn", "orby4middleware.app:app", "--host", "0.0.0.0", "--port", "8080"]
