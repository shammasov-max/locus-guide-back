-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable pg_trgm for potential fuzzy search in future
CREATE EXTENSION IF NOT EXISTS pg_trgm;
