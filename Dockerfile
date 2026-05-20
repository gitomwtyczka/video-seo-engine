# Video SEO Engine — Production Dockerfile
# Target: Oracle ARM VPS (aarch64) + x86_64 compatible
# Base: python:3.11-slim (Debian Bookworm)

FROM python:3.11-slim

# ---- System deps ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# ---- App setup ----
WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python deps + extras needed in production
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pyyaml

# Copy source code
COPY . .

# ---- Runtime directories ----
# These are typically bind-mounted from host in production
# but created here so the container works standalone
RUN mkdir -p \
    data/prawy/subs \
    data/prawy/seo_results \
    data/prawy/registry \
    cookies \
    logs \
    profiles

# ---- Non-root user for security ----
RUN useradd -m -u 1001 vse
RUN chown -R vse:vse /app
USER vse

# ---- Default command (override in docker-compose) ----
CMD ["python", "-m", "cli.main", "--help"]
