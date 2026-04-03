FROM python:3.12-slim

WORKDIR /app

# lxml needs libxml2/libxslt; everything else ships as a wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "telegram_bot.py"]
