FROM python:3.8.5-slim

RUN mkdir -p /teamo/db
WORKDIR /teamo

COPY dist/* /teamo/

RUN python3 -m pip install --no-index --find-links=/teamo teamo

VOLUME /teamo/db

CMD ["python3", "-m", "teamo", "--database", "/teamo/db/teamo.db"]
