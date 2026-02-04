# Airwave Justfile

set shell := ["powershell.exe", "-c"]

# Install all dependencies (Backend + Frontend)
install: install-backend install-frontend

# Install Backend Dependencies (Poetry)
install-backend:
    cd backend && poetry install

# Install Frontend Dependencies (npm)
install-frontend:
    cd frontend && npm install

# Run the entire stack (Mock for now, will eventually run parallel)
dev:
    echo "Starting Airwave Dev Environment..."
    # parallelly executing eventually

# Run Backend Tests
test-backend:
    cd backend && poetry run pytest

# Run Frontend Tests
test-frontend:
    cd frontend && npm test

# Lint Backend
lint-backend:
    cd backend && poetry run ruff check .
    cd backend && poetry run mypy .

# Build for Production
build:
    echo "Building Airwave..."
