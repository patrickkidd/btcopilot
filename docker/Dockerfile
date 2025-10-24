FROM python:3.11.6-alpine

# RUN apk add --no-cache postgresql-libs gcc g++ musl-dev postgresql-dev
# # g++ libpq-dev gcc unixodbc unixodbc-dev
RUN apk add --update alpine-sdk libpq-dev

RUN pip install --upgrade pip
RUN pip install pipenv

COPY Pipfile .
RUN mkdir .venv
RUN pipenv install

COPY btcopilot ./btcopilot

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# ENV PYTHONPATH /server
ENV FLASK_APP btcopilot
ENV FLASK_ADMIN_EMAIL info@alaskafamilysystems.com
ENV FLASK_MAIL_SERVER smtp-relay.sendinblue.com
ENV FLASK_MAIL_PORT 587
ENV FLASK_MAIL_DEFAULT_SENDER info@alaskafamilysystems.com
ENV FLASK_STRIPE_ENABLED False

CMD ["pipenv", "run", "python", "-m", "btcopilot"]
