-- Caso C-14: los seis UPDATE y DELETE rechazados por el disparador, y el INSERT rechazado por la clave foránea.
-- Antes de correr este archivo: python seed.py (sin filas, un disparador FOR EACH ROW no llega a ejecutarse).
-- Se corre con: psql -U postgres -h localhost -d taller -f test/solo_agregado.sql
-- Cada sentencia tiene que terminar en ERROR, y por eso ninguna cambia nada. psql sigue con la siguiente.

\encoding UTF8

\echo '--- 1. UPDATE sobre historial_estado_orden: lo rechaza el disparador'
UPDATE historial_estado_orden SET hasta_estado = 'CANCELADA';

\echo '--- 2. DELETE sobre historial_estado_orden: lo rechaza el disparador'
DELETE FROM historial_estado_orden;

\echo '--- 3. UPDATE sobre movimiento_stock: lo rechaza el disparador'
UPDATE movimiento_stock SET cantidad = 999;

\echo '--- 4. DELETE sobre movimiento_stock: lo rechaza el disparador'
DELETE FROM movimiento_stock;

\echo '--- 5. UPDATE sobre historial_precio_repuesto: lo rechaza el disparador'
UPDATE historial_precio_repuesto SET precio_nuevo = 1;

\echo '--- 6. DELETE sobre historial_precio_repuesto: lo rechaza el disparador'
DELETE FROM historial_precio_repuesto;

\echo '--- 7. Una orden con un estado que no está en el catálogo: la rechaza la clave foránea'
INSERT INTO orden_trabajo (vehiculo_id, estado, falla, creada_en, total)
VALUES (1, 'NO_EXISTE', 'Estado inexistente', now(), 0);
