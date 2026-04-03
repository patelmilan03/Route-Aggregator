# Use the official, lightweight Python 3.11 image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and force stdout logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker's caching layers
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port Uvicorn will listen on
EXPOSE 8000

# Start Uvicorn. Note the 0.0.0.0 host - this is required for Docker routing!
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

