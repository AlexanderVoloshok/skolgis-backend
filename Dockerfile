# Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # опционально ускорить pip
    PIP_DISABLE_PIP_VERSION_CHECK=1

# системные зависимости при необходимости (psycopg2, GDAL и т.п.)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential gcc && rm -rf /var/lib/apt/lists/*

# создаём юзера без root
RUN useradd -m appuser

WORKDIR /app

# Устанавливаем системные зависимости для psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# сначала зависимости, чтобы кешировались
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# затем код
COPY . /app

# права
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8000", "main:app"]
