FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Ho_Chi_Minh

WORKDIR /app

COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8000"]
