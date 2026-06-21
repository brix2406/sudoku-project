FROM python:3.11-slim

WORKDIR /usr/src/app

RUN pip install --no-cache-dir pytest requests nats-py

COPY e2e_tests/ ./e2e_tests/

WORKDIR /usr/src/app/e2e_tests

CMD ["pytest", "-m", "e2e", "-v"]
