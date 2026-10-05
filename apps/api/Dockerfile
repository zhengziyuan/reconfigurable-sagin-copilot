FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RSAGIN_HOST=0.0.0.0

WORKDIR /app

COPY packages/rsagin-core ./packages/rsagin-core
COPY apps/api ./apps/api
COPY configs ./configs
COPY runs/.gitkeep ./runs/.gitkeep

RUN pip install --no-cache-dir ./packages/rsagin-core ./apps/api

EXPOSE 8000

CMD ["python", "apps/api/main.py"]
