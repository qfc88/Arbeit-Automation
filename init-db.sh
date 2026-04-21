#!/bin/bash
set -e

echo "Starting user initialization script..."

# Create postgres user with superuser privileges if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'postgres') THEN
            CREATE USER postgres WITH SUPERUSER CREATEDB CREATEROLE LOGIN PASSWORD '$POSTGRES_PASSWORD';
            GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO postgres;
            RAISE NOTICE 'Created postgres user successfully';
        ELSE
            ALTER USER postgres PASSWORD '$POSTGRES_PASSWORD';
            GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO postgres;
            RAISE NOTICE 'Updated postgres user password';
        END IF;
    END
    \$\$;
EOSQL

echo "User initialization completed successfully"