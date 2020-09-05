FROM python:3.8.5-slim

RUN mkdir -p /teamo/db
WORKDIR /teamo

COPY teamo /teamo
COPY setup.py README.md LICENSE /teamo/

RUN python3 -m pip install /teamo

VOLUME /teamo/db

CMD ["python3", "-m", "teamo", "/teamo/db"]
