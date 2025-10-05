# 1. Base image
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Copy dependencies
COPY requirements.txt .

# 4. Cài đặt dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy toàn bộ code
COPY . .

# 6. Expose port 8080 (Fly.io dùng port này)
EXPOSE 8080

# 7. Chạy Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
