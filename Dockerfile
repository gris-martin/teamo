FROM python:3.8.5-alpine

# See https://stackoverflow.com/a/61608842
RUN apk add build-base

RUN mkdir -p /teamo/db
WORKDIR /teamo

ARG VERSION
COPY dist/teamo-${VERSION}-py3-none-any.whl /teamo/

RUN python3 -m pip install /teamo/teamo-${VERSION}-py3-none-any.whl

VOLUME /teamo/db

CMD ["python3", "-m", "teamo", "--database", "/teamo/db/teamo.db"]
