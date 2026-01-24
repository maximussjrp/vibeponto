-- Script de inicialização do PostgreSQL
-- Executado automaticamente pelo Docker na primeira vez

-- Habilitar extensões
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Para busca fuzzy

-- TimescaleDB já vem habilitado na imagem

-- Criar schema
CREATE SCHEMA IF NOT EXISTS vibeponto;

-- Configurar search_path
ALTER DATABASE vibeponto SET search_path TO vibeponto, public;

-- Comentário
COMMENT ON DATABASE vibeponto IS 'VibePonto - Sistema de Ponto Eletrônico';
