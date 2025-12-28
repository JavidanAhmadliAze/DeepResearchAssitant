# 1. Start with a slim version of Python 3.13
FROM python:3.13-slim-bookworm

# 2. Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Ensures the app can find your local modules
ENV PYTHONPATH=/app

# 3. Install Linux system libraries
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Working directory
WORKDIR /app

# 5. Copy and install requirements FIRST (for layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of the project
COPY . .

# 7. Default port (FastAPI)
EXPOSE 8000
# Default port (Streamlit)
EXPOSE 8501

# Default CMD (Overridden by docker-compose)
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]