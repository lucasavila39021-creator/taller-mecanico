# BITÁCORA — TP Taller Mecánico

> El parte de cambio de turno: qué se hizo, qué se decidió y qué sigue.
> Actualizar al cerrar cada fase. Lo más nuevo va arriba en "Registro".

## Estado de fases
| # | Fase | Ejercicios | Estado |
|---|------|-----------|--------|
| 0 | Entorno: PostgreSQL, repo, venv, docs | – | ✅ |
| 1 | Config, database, lifespan, health | Ej 1 | ✅ |
| 2 | Modelos, migraciones (auto + trigger a mano), seed.py | Ej 2, 7 | ✅ |
| 3 | BaseRepository, SoftDelete, UoW, paginación | Ej 6 | ✅ |
| 4 | Auth y autorización (bcrypt, login, cookie, roles, grupos de rutas) | Ej 4, 5 | ✅ |
| 5 | Clientes, vehículos y repuestos (stock en un único punto, historial de precios) | Ej 3 | ✅ |
| 6 | Órdenes: alta, transiciones, terminar, cancelar, sin N+1, aviso | Ej 6, 8 | ✅ |
| 7 | test/*.http (C-01 a C-19), solo_agregado.sql, evidencias, README | – | ✅ |

## Decisiones tomadas
- 30/10 · Guía única: el enunciado de 22 páginas. El material de la cátedra no tiene las secciones que cita el TP.
- 30/10 · PostgreSQL 17.11 nativo en Windows: ya estaba instalado y cumple el mínimo 16 del enunciado, que no pide Docker. `psql` viene incluido y se necesita para la evidencia del caso C-14.
- 30/10 · Python 3.14. asyncpg 0.32 instaló e importa bien en Python 3.14; la conexión real se prueba en la Fase 1.
- 30/10 · Roles de cada IA: Claude Code (VS Code) escribe y prueba el código; el chat de claude.ai planifica, explica y revisa; Gemini extrae y resume el material y hace tareas sueltas que Claude revisa. **Una sola IA escribe código.**
- 31/10 · Sin endpoint para desactivar usuarios: no está en la tabla del enunciado. `get_usuario_actual` y el login igual rechazan a un usuario con `activo` en falso, como pide el Ejercicio 5.
- 31/10 · RN-06: con el cambio de contraseña pendiente se pueden usar todas las rutas de `/auth` y las de salud, como dice el enunciado, no sólo el cambio de contraseña.
- 31/10 · Contraseña actual incorrecta en `/auth/cambiar-password`: 401, porque el enunciado sólo lista 200, 401 y 422 para esa ruta.
- 31/10 · `POST /usuarios` recibe `email`, `nombre` y `password`, sin rol: los roles se asignan con `POST /usuarios/{id}/roles`. El enunciado no fija el cuerpo.
- 31/10 · El intento rechazado con 429 no se anota en `intento_acceso`: no se verificó ninguna contraseña, y el caso C-05 espera cinco fallos en la tabla.
- 31/10 · `Retry-After`: los segundos que faltan para que venza el fallo más viejo de los que cuentan.
- 31/10 · Sin `GET /clientes` (lista paginada): Lucas lo mencionó, pero no está en la tabla del enunciado, y pidió "endpoints exactos de la tabla". Sí están `POST /clientes` y `GET /clientes/{id}`.
- 31/10 · `POST /clientes` no recibe `usuario_id`: la cuenta llega sólo por el auto-registro, y RN-02 no deja apropiarse de una ficha.
- 31/10 · `/mis-vehiculos`, `/repuestos/{id}/movimientos` y `/repuestos/{id}/precios` devuelven una lista sin envoltorio: la tabla no les da `page` ni `size`.
- 31/10 · Patente y código se guardan en mayúsculas, para que `ac456ef` choque con `AC456EF`.
- 31/10 · `stock_inicial` admite 0: en ese caso no hay movimiento, porque el CHECK pide cantidad distinta de cero.
- 31/10 · Cantidad de `stock_inicial` y de reposición: máximo 1.000.000. Pasar del máximo de la columna da 422. El enunciado no fija estos límites.
- 31/10 · Un repuesto dado de baja da 404 en todas sus rutas, incluidas `/movimientos` y `/precios`: RN-16 dice que deja de aparecer.
- 31/10 · Motivo de la reposición: "Reposición". El enunciado sólo fija "Stock inicial".
- 31/10 · `POST /ordenes/{id}/iniciar` sólo con el rol MECANICO: la tabla no incluye a ADMIN.
- 31/10 · `terminar`: el permiso se evalúa antes que el estado, igual que RN-12 para cancelar. Otro mecánico recibe 403 aunque el estado no lo permita. El mecánico asignado tiene que seguir teniendo el rol (RN-04).
- 31/10 · Un repuesto dado de baja después del alta de la orden igual se descuenta al terminarla: RN-16 sólo prohíbe usarlo en órdenes nuevas.
- 31/10 · `GET /ordenes` y `GET /mis-ordenes` devuelven un resumen sin ítems ni historial. El enunciado sólo muestra el cuerpo del detalle.
- 31/10 · Un total que no entra en `NUMERIC(12,2)` da 422. Sin este control sería un 500.
- 31/10 · Motivo de la salida de stock: "Salida por la orden N". El aviso va al logger `uvicorn.error`, el que ya sale en la consola del servidor.
- 31/10 · Se mantiene afuera `GET /clientes`: agregar lo que el enunciado no pide no suma nota.
- 31/10 · Contraseñas en los `.http`: cada archivo declara la de mentira de `seed.py` en `@password`, con un comentario que lo aclara. Los logins la necesitan.

## Registro
### 31/10 · Fase 7
- `test/*.http` con C-01 a C-13 y C-15 a C-19, y `test/solo_agregado.sql` con C-14. `README.md` con la puesta en marcha y la entrega.
- Verificado con un ejecutor propio contra uvicorn, con `seed.py` antes de cada archivo: 81 pedidos, 0 fallas. No había Node para correr httpyac.
- REST Client: Lucas probó a mano `01_autenticacion.http`, y funcionó todo. `02`, `03` y `04` se verificaron sólo con el ejecutor propio.
- Evidencias en `docs/evidencias/`: `C-14-psql.png` (los 6 rechazos del disparador y el de la clave foránea) y `C-15-consola.txt` (5 SELECT en el detalle de la orden con 2 ítems y 5 en la de 4).
- C-12: el aviso aparece en el registro después de la línea del `POST /ordenes/2/terminar` con 200.
- `test/solo_agregado.sql` con psql: 7 rechazos, sin cambios en las filas.
- Desde un clon limpio de GitHub, con venv nuevo y base vacía: sin `.env` no arranca; `upgrade head`, `downgrade base`, `upgrade head`, `seed.py` y el servidor andan, y los 81 pedidos también.
- Ninguna credencial real en los archivos ni en el historial de Git.

### 31/10 · Fase 6
- Módulo ordenes: catálogo de sólo lectura, alta (RN-10), listados, detalle, iniciar, terminar (RN-13) y cancelar (RN-12).
- Probados C-06, C-10, C-11, C-12 (con el servidor real: el aviso sale después de la respuesta), C-13, C-15 y C-17 contra la base real.
- El detalle usa 5 consultas con 2 y con 4 ítems: 2 de la sesión y 3 de la orden.

### 31/10 · Fase 5
- Módulo clientes: `POST /clientes`, `GET /clientes/{id}` con vehículos vigentes, `POST /clientes/{id}/vehiculos`, `DELETE /vehiculos/{id}` (RN-16) y `GET /mis-vehiculos` (RN-17).
- Módulo repuestos: listado con `q`, detalle, alta con `stock_inicial`, `PATCH` con su línea de precio en el mismo bloque (RN-20), baja lógica, reposición, movimientos y precios.
- Stock: `RepuestoRepository.registrar_movimiento` es el único punto que lo escribe (RN-14). La terminación de órdenes de la Fase 6 tiene que usarlo.
- Los 422 de validación salen en español, y `PaginaInexistente` se traduce en cada router.
- Probados C-01, C-16, C-18 y C-19 contra la base real, y `GET /repuestos?size=2` idéntico al ejemplo de la pág. 18.

### 31/10 · Fase 4
- 4c: `POST /auth/login` y `POST /auth/logout`. Primero el límite (RN-08), después la verificación contra el hash real o el ficticio (RN-09). `intento_acceso` en sesión y transacción propias.
- 4d: `get_usuario_actual`, `requiere_rol`, `exigir_password_al_dia`, `GET /auth/yo`, `POST /auth/cambiar-password` (RN-07) y los dos grupos de rutas en `main.py`.
- 4e: `POST /usuarios`, roles (asignar, listar y revocar, RN-03 y RN-05) y `GET /eventos`. Los administradores se bloquean con `FOR UPDATE` antes de contarlos.
- Probados C-01 a C-05, C-07 y C-08 contra la base real, y C-09 en lo que depende de esta fase. C-06 quedó parcial: falta la parte de las órdenes (Fase 6). Faltan los `.http` y sus evidencias (Fase 7).
- Corrección: un vencimiento en el límite del calendario daba 500 al pasarlo a UTC. Ahora da 422.
- 4a: `app/core/security.py` con bcrypt en `to_thread` y bajo semáforo, y JWT con `iat` con decimales. El semáforo y el hash ficticio se crean en el lifespan y van a `app.state`.
- 4b: `POST /auth/registro` (RN-02) con el circuito completo de capas. Probado el caso C-02 contra la base real.
- Corrección del 4b: un manejador en `main.py` hace que el 422 no repita la entrada. Antes devolvía la contraseña, y un carácter inválido terminaba en un 500.

### 30/10 · Fase 3
- `BaseRepository[T]` y `SoftDeleteRepository[T]` en `app/core/repository.py`: `add`, `update` y `delete` hacen `flush()`, nunca `commit()`; `get_all` y `count` reciben los mismos filtros.
- `UnitOfWork` base en `app/core/unit_of_work.py`: confirma al salir, revierte si hay excepción y no cierra la sesión.
- Corrección: si fallaba el propio `commit`, la sesión quedaba inservible (`PendingRollbackError`). Ahora hace `rollback` y vuelve a lanzar la excepción.
- Paginación en `app/core/paginacion.py`: envoltorio `{items, total, page, size, pages}`. La página inexistente lanza `PaginaInexistente`, sin HTTP, porque traducir los errores le toca al router.
- Probado contra la base real, con `seed.py` al final. La traducción a 422 de `PaginaInexistente` todavía no está probada.
- Los repositorios y Unit of Work de cada módulo se hacen junto con cada módulo, en las Fases 4 a 6.

### 30/10 · Fase 2
- Modelos de las 13 tablas en los módulos usuarios, clientes, repuestos y ordenes, con `lazy="raise"`.
- Migración 1 con `--autogenerate` y migración 2 a mano, con el disparador de sólo agregado sobre las 3 tablas. `upgrade head` → `downgrade base` → `upgrade head` anduvo con las dos.
- Prueba en una transacción con ROLLBACK: 6 rechazos del disparador y 1 de la clave foránea; la base quedó vacía. Evidencia C-14 pendiente para la Fase 7.
- `seed.py` vacía con `TRUNCATE ... RESTART IDENTITY`, porque el ROLLBACK no devuelve los números de las secuencias y los casos de prueba usan ids fijos. Corrido dos veces: mismo resultado, ids incluidos; sólo cambia `password_hash`, por la sal de bcrypt.
- `hashear_password` en `app/core/security.py`.

### 30/10 · Fase 1
- `config.py`, `database.py`, lifespan en `main.py` y módulo `health`.
- Pruebas contra la base real, hechas por Lucas:
  - Base levantada: live 200, ready 200 (la contraseña real conecta).
  - `postgresql-x64-17` detenido: live 200, ready 503 con "La base de datos no está disponible".
  - Base de vuelta, sin reiniciar la app: ready 200 (`pool_pre_ping`).

### 30/10 · Fase 0
- Plan maestro definido. Se crearon CLAUDE.md y esta bitácora.
- Repo Git creado (commit 40c6fdd). `.gitignore` con `.env` protegido.
- venv con Python 3.14. `requirements.txt` instalado (SQLAlchemy 2.1.6, SQLModel 0.0.48).

## Pendientes
- Entrega: la auditoría final del repo, y después armar `LucasAvila.zip` con el comando del `README.md`.

## Próximo paso
Auditoría final del repo, a cargo de Lucas. Después, armar el `.zip` y entregar.
