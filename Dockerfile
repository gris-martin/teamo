FROM python:3.8.5-alpine

RUN mkdir -p /teamo/db
WORKDIR /teamo

COPY *.py requirements.txt /teamo/

VOLUME /teamo/db

CMD ["python", "teamo.py"]
