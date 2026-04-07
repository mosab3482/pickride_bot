-- PickRide PostgreSQL Setup Script
-- Run this file once to create the database

CREATE DATABASE pickride;

\c pickride;

-- All tables are created automatically by the bot on first launch
-- via database.init_db()

-- Optional: Create a dedicated user
-- CREATE USER pickride_user WITH PASSWORD 'your_password';
-- GRANT ALL PRIVILEGES ON DATABASE pickride TO pickride_user;
