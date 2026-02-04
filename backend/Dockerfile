# Base Image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Configure Poetry: do not create virtualenv inside the container
RUN poetry config virtualenvs.create false

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root --without dev

# Copy the rest of the application code
COPY src/ ./src/

# Set environment variables
ENV PYTHONPATH="/app/src"
ENV DATA_DIR="/app/data"

# Ensure data directory exists
RUN mkdir -p /app/data

# Exposure Port
EXPOSE 8000

# Default Command: Start the API
CMD ["uvicorn", "airwave.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
