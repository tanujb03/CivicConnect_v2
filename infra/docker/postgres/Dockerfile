# CivicConnect development database: PostGIS + pgvector on the official postgis image.
# Build:  docker build -t civicconnect-postgres:local infra/docker/postgres      (scripts/dev/db_up.ps1 does this and starts the container)
# The tag is a build argument so the PostgreSQL/PostGIS pair can be changed without editing this file, e.g. --build-arg POSTGIS_TAG=16-3.4.
ARG POSTGIS_TAG=18-3.6
FROM postgis/postgis:${POSTGIS_TAG}

# PG_MAJOR is exported by the postgres base image; pgvector comes from the PGDG apt repository that image already configures.
RUN apt-get update \
    && apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-pgvector" \
    && rm -rf /var/lib/apt/lists/*
