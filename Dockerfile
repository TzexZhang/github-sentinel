FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 7680

CMD ["uv", "run", "python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "7680"]
