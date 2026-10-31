# CLAUDE.md — TP Taller Mecánico (Programación III · UTN Mendoza)

> **Toda sesión nueva (Claude Code, claude.ai o Gemini) empieza leyendo este archivo y `BITACORA.md`.**
> Este archivo guarda las decisiones FIJAS. La bitácora guarda el AVANCE.

## Contexto
- Alumno: Lucas. Entrega: **sábado 31/10/2026 a la noche**.
- Fuente de verdad ÚNICA: `docs/enunciado.pdf` (22 páginas). Se sigue al pie de la letra: no se omite nada de lo que pide y no se agrega nada que no pida.
- Para leer el enunciado usá `docs/enunciado.txt` (versión texto del PDF, una página por salto de página). Si hay diferencias, manda el PDF.
- Doble objetivo: aprobar **y** que Lucas entienda cada parte (puede tener que defenderlo).

## Forma de trabajo (obligatoria)
1. Pasos chicos. Antes del código: explicar la idea con un **ejemplo cotidiano**, después el código, después probarlo.
2. Preguntar si se entendió antes de pasar al siguiente paso.
3. Todo comando indica en qué terminal va: **cmd de Windows** o **terminal de VS Code**.
4. No tocar archivos de fases cerradas sin avisar y explicar por qué.
5. Al cerrar cada fase: actualizar `BITACORA.md` y hacer `git commit`.
6. Si el enunciado es ambiguo: preguntar. No inventar.
7. Los commits NO llevan la línea Co-Authored-By ni ninguna otra firma de IA.

## Stack y entorno
- Windows 10/11, **Python 3.14** (el mínimo es 3.12). PostgreSQL 17.11 nativo en Windows (cumple el mínimo 16 del enunciado). Base de datos: taller. Sin Docker.
- FastAPI ≥0.111 · SQLModel ≥0.0.24 · SQLAlchemy 2 async · asyncpg ≥0.30 · Alembic ≥1.13 con plantilla async · pydantic-settings 2 · bcrypt ≥4 · PyJWT ≥2.8.

## Reglas NO negociables (las mira la corrección)
**Capas:** Router → Service → UoW → Repository → Model. El router construye el UoW con una dependencia y se lo pasa al servicio; el servicio lo abre con `async with` y nunca lo construye.
**Repositorios:** `add`/`update` hacen `flush()`, **nunca `commit()`**. `BaseRepository[T](session, model)` con get_by_id, get_all, count, add, update, delete. `SoftDeleteRepository[T]` hereda, filtra dados de baja y agrega `get_by_id_including_deleted` y `soft_delete`. El repositorio de `EstadoOrden` es de sólo lectura y **no** hereda de BaseRepository.
**UoW:** confirma al salir del bloque, revierte si hay excepción, **no cierra la sesión**. Uno por módulo. RN-02, RN-13 y RN-20 van cada una en un solo bloque.
**Lecturas:** precarga (selectinload/joinedload) declarada **dentro** del método del repo. Carga perezosa prohibida. El detalle de una orden se resuelve con una cantidad fija de consultas.
**Esquema:** sólo Alembic, nunca `create_all`. Migración 1 con `--autogenerate`; migración 2 **a mano** con el disparador de sólo agregado (3 tablas). Cada una lleva un comentario que diga que se revisó antes de aplicarla. `upgrade head` → `downgrade base` → `upgrade head` tiene que andar.
**Modelo:** nombres de tablas y columnas **exactos** del enunciado (págs. 5-6). Dinero NUMERIC/`Decimal`, fechas `timestamptz`, índice en cada FK. Índices únicos parciales con `postgresql_where`.
**Unicidad:** la garantiza la base, nunca una consulta previa. `IntegrityError` → 409 con mensaje propio, nunca el texto de la base.
**Secretos:** `SECRET_KEY` y `POSTGRES_PASSWORD` sin valor por defecto (si faltan, no arranca). `.env` nunca se versiona; `env.example` sí.
**Ciclo de vida:** motor y fábrica de sesiones se crean en el lifespan y van a `app.state`. `get_session` usa `expire_on_commit=False`. El hash ficticio se calcula una vez en el lifespan. `dispose()` al apagar.
**bcrypt:** `asyncio.to_thread` + semáforo, costo en la config, hash **antes** de abrir la transacción, contraseñas de **máximo 72 bytes** (bytes, no caracteres).
**Token:** JWT con sub, iat (con fracciones de segundo), exp y roles. Viaja **sólo** en la cookie `access_token` (HttpOnly, SameSite=Lax, Max-Age, Secure configurable). Nunca en el cuerpo ni en la cabecera Authorization.
**Login:** 1) límite: 5 fallos del mismo email+ip en 60 s → 429 con Retry-After y sin calcular hash; 2) verificar contra el hash real o el ficticio. `intento_acceso` se escribe en una sesión y transacción **propias**, con un comentario que explique el costo.
**Autorización:** los roles vigentes se consultan en la base en cada petición. 401 (quién sos) ≠ 403 (no podés). Dos grupos de rutas en `main.py`. `/ordenes/{id}/cancelar` no lleva requiere_rol.
**Contratos:** separados de los modelos, `extra="forbid"`, PATCH con `exclude_unset`, envoltorio `{items,total,page,size,pages}`. Ningún 500 por entrada inválida.
**Async:** todos los handlers con `async def`. El aviso al cliente va con BackgroundTasks.

## Estructura
```
main.py · seed.py · alembic.ini · requirements.txt · env.example · README.md
app/core/{config,database,security,dependencies,repository,paginacion,unit_of_work}.py
app/modules/health/router.py
app/modules/{usuarios,clientes,repuestos,ordenes}/{models,schemas,repository,unit_of_work,service,router}.py
migrations/   test/*.http   test/solo_agregado.sql   docs/
```

## Cómo arrancar una sesión nueva
1. Leer `CLAUDE.md` y `BITACORA.md`.  2. `git log --oneline -10`.
3. Decir en qué fase estamos y cuál es el próximo paso.  4. Esperar el OK de Lucas.
