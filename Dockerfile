FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY netbox.py .
COPY server.py .
COPY validation.py .

CMD ["python", "server.py"]
