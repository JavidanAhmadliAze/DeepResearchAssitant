# ======== Base Image ========
FROM python:3.13-slim

# ======== Environment Variables ========
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# ======== Set Working Directory ========
WORKDIR /app

# ======== Install System Dependencies ========
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ======== Install uv Project Manager ========
RUN pip install --upgrade pip
RUN pip install uv

# ======== Copy Project Files ========
COPY pyproject.toml uv.lock /app/
COPY src/ /app/src/
COPY config/ /app/config/
COPY data/ /app/data/
COPY frontend/ /app/frontend/

# ======== Install Python Dependencies ========
RUN uv install --no-dev

# ======== Expose Streamlit Port ========
EXPOSE 8501

# ======== Default Command ========
CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
