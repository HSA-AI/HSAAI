#!/usr/bin/env bash
set -euo pipefail
: "${APP_DB_PASSWORD:?Set runtime password}"
: "${MIGRATION_DB_PASSWORD:?Set separate migration password}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
  --set=app_password="$APP_DB_PASSWORD" --set=migration_password="$MIGRATION_DB_PASSWORD" <<'SQL'
ALTER ROLE hsaai_app NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT LOGIN;
ALTER ROLE hsaai_admin NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT LOGIN;
ALTER ROLE platform_svc NOLOGIN;
SELECT format('ALTER ROLE hsaai_app PASSWORD %L', :'app_password') \gexec
SELECT format('ALTER ROLE hsaai_admin PASSWORD %L', :'migration_password') \gexec
GRANT CONNECT ON DATABASE hsaai TO hsaai_app, hsaai_admin;
GRANT USAGE, CREATE ON SCHEMA public TO hsaai_admin;
GRANT USAGE ON SCHEMA public TO hsaai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE hsaai_admin IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hsaai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE hsaai_admin IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO hsaai_app;
SQL

: "${KEYCLOAK_DB_PASSWORD:?Set a separate identity database password}"
: "${MLFLOW_DB_PASSWORD:?Set a separate MLflow database password}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
 --set=identity_password="$KEYCLOAK_DB_PASSWORD" --set=mlflow_password="$MLFLOW_DB_PASSWORD" <<'SQL'
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='keycloak_app') THEN CREATE ROLE keycloak_app LOGIN NOSUPERUSER NOBYPASSRLS; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mlflow_app') THEN CREATE ROLE mlflow_app LOGIN NOSUPERUSER NOBYPASSRLS; END IF;
END $$;
SELECT format('ALTER ROLE keycloak_app PASSWORD %L', :'identity_password') \gexec
SELECT format('ALTER ROLE mlflow_app PASSWORD %L', :'mlflow_password') \gexec
ALTER DATABASE keycloak OWNER TO keycloak_app;
ALTER DATABASE mlflow OWNER TO mlflow_app;
SQL
psql --username "$POSTGRES_USER" --dbname keycloak --set=ON_ERROR_STOP=1 --command 'GRANT USAGE,CREATE ON SCHEMA public TO keycloak_app;'
psql --username "$POSTGRES_USER" --dbname mlflow --set=ON_ERROR_STOP=1 --command 'GRANT USAGE,CREATE ON SCHEMA public TO mlflow_app;'
