FROM python:3.12-slim

ARG RUNTIME_UID=1000
ARG RUNTIME_GID=1000

RUN groupadd --gid "${RUNTIME_GID}" secfusion \
    && useradd --uid "${RUNTIME_UID}" --gid "${RUNTIME_GID}" --create-home secfusion

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY --chown=secfusion:secfusion . .

ENV PATH="/app/.venv/bin:$PATH"
ENV HOME="/home/secfusion"

USER secfusion

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
