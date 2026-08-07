FROM mcr.microsoft.com/entra-sdk/auth-sidecar@sha256:495ec1a7142b3e016b7d9b96ca73cfc6bb504f1c6b4ce07647dd5723275b1b7b AS auth-sidecar

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

RUN apt-get update     && apt-get install --yes --no-install-recommends git ca-certificates     && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/demo2-3-bank-servicing-agent

COPY demo2-3-bank-servicing-agent/evaluation/assert/ evaluation/assert/

RUN rm -rf evaluation/assert/.runtime \
    && python evaluation/assert/scripts/bootstrap_assert.py --install \
    && rm -rf evaluation/assert/.runtime/source/.git

ENV DOTNET_ROOT=/usr/share/dotnet     DOTNET_RUNNING_IN_CONTAINER=true     DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=true

COPY --from=auth-sidecar /usr/share/dotnet /usr/share/dotnet
COPY --from=auth-sidecar /app /opt/entra-auth-sidecar

ENTRYPOINT ["python", "evaluation/assert/scripts/run_assert_composite.py"]
CMD ["validate"]
