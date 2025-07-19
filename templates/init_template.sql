-- PostgreSQL initialization script for Open-WebUI
-- Generated from template with environment variables

-- Create database if it doesn't exist
SELECT 'CREATE DATABASE $OPENWEBUI_DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$OPENWEBUI_DB_NAME')\gexec

-- Connect to the database
\c $OPENWEBUI_DB_NAME

-- Create user if it doesn't exist
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = '$OPENWEBUI_DB_USER') THEN
        CREATE USER $OPENWEBUI_DB_USER WITH PASSWORD '$OPENWEBUI_DB_PASSWORD';
    END IF;
END
\$\$;

-- Grant necessary permissions for Open-WebUI
GRANT CONNECT ON DATABASE $OPENWEBUI_DB_NAME TO $OPENWEBUI_DB_USER;
GRANT USAGE ON SCHEMA public TO $OPENWEBUI_DB_USER;
GRANT CREATE ON SCHEMA public TO $OPENWEBUI_DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $OPENWEBUI_DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $OPENWEBUI_DB_USER;

-- Grant default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $OPENWEBUI_DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $OPENWEBUI_DB_USER;

-- Optional: Create extensions that Open-WebUI might need
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set user as owner of the database for full control
ALTER DATABASE $OPENWEBUI_DB_NAME OWNER TO $OPENWEBUI_DB_USER;

\echo 'Database initialization completed successfully!'
\echo 'User: $OPENWEBUI_DB_USER'
\echo 'Database: $OPENWEBUI_DB_NAME'
