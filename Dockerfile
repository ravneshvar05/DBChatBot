# Use official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install cryptography  # Needed for some SSL connections (Aiven)

# Copy the application code
COPY . .

# Create a non-root user (Hugging Face requirement)
RUN useradd -m -u 1000 user
RUN chown -R user:user /app
USER user

# Make the start script executable
RUN chmod +x start.sh

# Expose the port that Hugging Face expects
EXPOSE 7860

# Run the start script
CMD ["./start.sh"]
