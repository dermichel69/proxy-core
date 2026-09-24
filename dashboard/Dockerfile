FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends docker.io && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask requests[socks]
WORKDIR /app
COPY app.py .
COPY templates/ templates/
EXPOSE 8080
CMD ["python", "app.py"]
