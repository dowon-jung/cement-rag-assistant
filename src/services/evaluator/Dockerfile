FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc curl && rm -rf /var/lib/apt/lists/*
COPY ../../shared ./shared
COPY . ./service
RUN pip install --no-cache-dir -e ./service
CMD ["python", "-m", "service.main"]
