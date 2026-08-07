FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false \
    AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=false \
    AZURE_TRACING_GEN_AI_INCLUDE_BINARY_DATA=false

WORKDIR /app

COPY pyproject.toml ./
COPY main.py ./
COPY instructions.md ./
COPY tools.json ./
COPY .agent_configs ./.agent_configs
COPY skills ./skills
COPY bank_servicing_agent ./bank_servicing_agent

RUN pip install --no-cache-dir .

CMD ["python", "main.py"]
