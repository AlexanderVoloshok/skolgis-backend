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
    libtiff-dev \
    libgeos-dev \
    libproj-dev \
    libsqlite3-dev \
    libbz2-dev \
    libffi-dev \
    zlib1g-dev \
    libpq-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://download.osgeo.org/gdal/3.2.1/gdal-3.2.1.tar.gz
RUN tar -xvzf gdal-3.2.1.tar.gz && cd gdal-3.2.1
RUN cd gdal-3.2.1 && \
    ./configure --prefix=/usr/local && \
    make -j$(nproc) && \
    make install && \
    ldconfig
RUN gdalinfo --version && \
    pip3 install pygdal=="`gdal-config --version`.*"

# сначала зависимости, чтобы кешировались
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# затем код
COPY . /app

# права
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8000", "src/main:app"]
