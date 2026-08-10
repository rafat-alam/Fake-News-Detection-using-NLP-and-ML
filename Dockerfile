# Use a lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Create a non-root user for better security
RUN useradd --create-home appuser

# Copy dependency file first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY . .

# Give the non-root user ownership of the application files
RUN chown -R appuser:appuser /app

# Run the application as a non-root user
USER appuser

# Render provides the PORT environment variable
EXPOSE 10000

# Start the FastAPI application
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]