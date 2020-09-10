FROM python:3.8.5-slim

RUN mkdir -p /teamo/db
WORKDIR /teamo

ARG VERSION
COPY dist/teamo-${VERSION}-py3-none-any.whl /teamo/

RUN python3 -m pip install /teamo/teamo-${VERSION}-py3-none-any.whl

ENV TEAMO_UPDATE_INTERVAL 15
ENV TEAMO_CHECK_INTERVAL 5

VOLUME /teamo/db

CMD ["python3", "-m", "teamo", "--database", "/teamo/db/teamo.db"]
