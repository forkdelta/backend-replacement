FROM python:3.6-alpine

RUN addgroup -S app && adduser -S -g app app
WORKDIR /usr/src/app

RUN apk --update --upgrade add --virtual deps \
      gcc python3-dev linux-headers musl-dev \
      alpine-sdk openssl-dev gmp-dev libffi-dev \
      postgresql-dev && \
    apk --update --upgrade add --no-cache libpq gmp

COPY ./requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN apk del deps

COPY . /usr/src/app
RUN chown -R app:app /usr/src/app

USER app

EXPOSE 8080
