FROM python:3.11-slim-bookworm

# CBC is the solver run.py drives; HiGHS needs no apt package because the
# highspy wheel vendors its own binary.
RUN apt-get update \
    && apt-get install -y --no-install-recommends coinor-cbc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY nemde/ ./nemde/
RUN uv sync --frozen --extra api

# Reports stamp this sha in their footer; the image has no .git to read it from.
ARG GIT_SHA=""

ENV PATH="/app/.venv/bin:$PATH" \
    MPLBACKEND=Agg \
    NEMDE_GIT_SHA=$GIT_SHA

EXPOSE 8000
CMD ["uvicorn", "nemde.api:app", "--host", "0.0.0.0", "--port", "8000"]
