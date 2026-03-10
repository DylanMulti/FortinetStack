FROM python:3.11-slim

WORKDIR /app

RUN pip install prometheus-client

COPY parser.py .

CMD ["python", "-u", "parser.py"]
