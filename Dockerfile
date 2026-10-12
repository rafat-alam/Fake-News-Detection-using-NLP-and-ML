# Use a lightweight Python image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Create a non-root user for better security
RUN useradd --create-home appuser

# Copy dependency file first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download NLP resources once while building; startup works without internet.
ENV NLTK_DATA=/usr/local/share/nltk_data
RUN python -m nltk.downloader -d /usr/local/share/nltk_data stopwords

# Redis runs locally alongside the API in this container.
RUN apt-get update \
    && apt-get install -y --no-install-recommends redis-server \
    && rm -rf /var/lib/apt/lists/*

# Copy the application source code
COPY . .

# Give the non-root user ownership of the application files
RUN mkdir -p /data && chown -R appuser:appuser /app /data

ENV REDIS_URL=redis://127.0.0.1:6379/0
VOLUME ["/data"]

# Repair mounted Redis volume ownership at startup, then drop to appuser
# before starting either Redis or the API.
USER root

# Render provides the PORT environment variable
EXPOSE 10000

# Start Redis first, then the API; stop both when either exits.
CMD ["python", "-m", "module.container_entrypoint"]
