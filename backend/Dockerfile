FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app


RUN pip install --no-cache-dir uv


COPY pyproject.toml uv.lock ./


RUN uv export --format requirements-txt --locked > /tmp/reqs.txt \
 && uv pip install --system -r /tmp/reqs.txt

COPY . .

EXPOSE 8000


CMD ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","8000","--reload"]
