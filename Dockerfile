FROM python:3.8.5-slim

RUN mkdir -p /teamo/db
WORKDIR /teamo

COPY *.py requirements.txt /teamo/

RUN python3 -m pip install -r requirements.txt

VOLUME /teamo/db

CMD ["python3", "teamo.py"]
