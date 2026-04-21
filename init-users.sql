-- Create postgres user with superuser privileges
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'postgres') THEN
        CREATE USER postgres WITH SUPERUSER CREATEDB CREATEROLE LOGIN PASSWORD 'working';
        RAISE NOTICE 'Created postgres user successfully';
    ELSE
        ALTER USER postgres PASSWORD 'working';
        RAISE NOTICE 'Updated postgres user password';
    END IF;
END
$$;

-- Grant all privileges on database
GRANT ALL PRIVILEGES ON DATABASE job_market_data TO postgres;