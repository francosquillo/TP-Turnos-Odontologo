-- Task 1.2 (D-04): habilita btree_gist para los EXCLUDE anti-solapamiento de C-04.
-- Montado en /docker-entrypoint-initdb.d; idempotente en rearranques.
CREATE EXTENSION IF NOT EXISTS btree_gist;
