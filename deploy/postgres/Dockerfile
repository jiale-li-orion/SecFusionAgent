ARG POSTGRES_BASE_IMAGE=public.ecr.aws/docker/library/postgres:16
FROM ${POSTGRES_BASE_IMAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && apt-get clean
