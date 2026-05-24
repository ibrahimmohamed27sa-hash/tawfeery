FROM python:3.11-slim

WORKDIR /app

# Expose port (default metadata, but actual binding uses environment variable)
EXPOSE 5050

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Start the Flask app using Gunicorn on the port specified by the $PORT environment variable, falling back to 5050
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5050} --workers 4 wsgi:app"]
