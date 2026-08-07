FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY bank_servicing_bridge ./bank_servicing_bridge
RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["python", "-m", "bank_servicing_bridge.activity_host"]
