FROM python:3.11-slim-bookworm

# System deps for PDF extraction + psycopg2 + psql client
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ libmupdf-dev mupdf-tools postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer-cached dependency install
COPY requirements.txt /app/requirements.txt
COPY requirements-dev.txt /app/requirements-dev.txt
COPY docker/requirements-docker.txt /app/docker/requirements-docker.txt
RUN pip install --no-cache-dir -r /app/docker/requirements-docker.txt

# Copy project
COPY . /app

# Create directories
RUN mkdir -p /app/logs /app/pdfs/downloaded /app/data/processed \
    /app/analysis_output/network_data /app/analysis_output/dashboard_data \
    /app/docs/data

CMD ["python", "scripts/export_static_site.py"]
