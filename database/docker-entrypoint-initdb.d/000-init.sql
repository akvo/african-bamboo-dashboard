CREATE USER akvo WITH PASSWORD 'password';

CREATE DATABASE african_bamboo_dashboard
WITH OWNER = akvo
     template = template0
     ENCODING = 'UTF-8'
     LC_COLLATE = 'en_US.UTF-8'
     LC_CTYPE = 'en_US.UTF-8';

\c african_bamboo_dashboard

CREATE EXTENSION IF NOT EXISTS ltree WITH SCHEMA public;
