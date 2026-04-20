FROM ubuntu:20.04
ARG DEBIAN_FRONTEND=noninteractive

RUN apt update && \
    apt upgrade -y && \
    apt install -y \
    git \
    vim \
    curl \
    wget \
    build-essential \
    make \
    cmake \
    tar \
    gcc \
    g++ \
    libtiff-dev \
    libgeos-dev \
    libproj-dev \
    libsqlite3-dev \
    libbz2-dev \
    libffi-dev \
    zlib1g-dev \
    libpq-dev \
    libssl-dev

RUN apt update --fix-missing && \
    apt upgrade -y && \
    apt install python3-pip -y && \
    apt install python3.9-dev -y && \
    apt install python-is-python3 -y && \
    pip3 install --upgrade pip

RUN wget https://download.osgeo.org/gdal/3.2.1/gdal-3.2.1.tar.gz
RUN tar -xvzf gdal-3.2.1.tar.gz && cd gdal-3.2.1
RUN cd gdal-3.2.1 && \
    ./configure --prefix=/usr/local && \
    make -j$(nproc) && \
    make install && \
    ldconfig
RUN gdalinfo --version && \
    pip3 install pygdal=="`gdal-config --version`.*"

WORKDIR /skolgis_backend
COPY . /skolgis_backend

RUN pip3 install -r requirements.txt

# права на entrypoint
RUN chmod +x /src/cleanup/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:5000", "src.main:app"]
