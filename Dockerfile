FROM python:3.12-alpine
RUN apk add --no-cache bash git docker-cli curl
WORKDIR /app
COPY webhook.py .
CMD ["python", "-u", "webhook.py"]
