FROM python:3.6-alpine

RUN addgroup -S app && adduser -S -g app app
WORKDIR /usr/src/app

RUN apk --update --upgrade add --virtual deps gcc python3-dev linux-headers musl-dev postgresql-dev && \
    apk --update --upgrade add --no-cache libpq

COPY ./requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN apk del deps

COPY . /usr/src/app
RUN chmod +x /usr/src/app/contract_observer.py
RUN chown -R app:app /usr/src/app

USER app
