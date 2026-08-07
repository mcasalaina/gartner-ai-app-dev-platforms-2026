FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY bank_servicing_backend ./bank_servicing_backend
RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "bank_servicing_backend.app:create_default_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
