# 1. Base image
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Cài system dependencies cần thiết cho psycopg2 và build package
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy dependencies
COPY requirements.txt .

# 5. Cài đặt dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy toàn bộ code
COPY . .

# 7. Expose port 8080 (Fly.io dùng port này)
EXPOSE 8080

# 8. Chạy Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]

