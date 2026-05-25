FROM python:3.11-slim

WORKDIR /app

EXPOSE 5050

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# gevent workers: each worker handles hundreds of concurrent connections
# 2 workers × 1000 conns each = handles 2000 simultaneous requests
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5050} --worker-class gevent --worker-connections 1000 --workers 2 --timeout 60 wsgi:app"]
