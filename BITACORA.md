# BITÁCORA — TP Taller Mecánico

> El parte de cambio de turno: qué se hizo, qué se decidió y qué sigue.
> Actualizar al cerrar cada fase. Lo más nuevo va arriba en "Registro".

## Estado de fases
| # | Fase | Ejercicios | Estado |
|---|------|-----------|--------|
| 0 | Entorno: PostgreSQL, repo, venv, docs | – | ⏳ en curso |
| 1 | Config, database, lifespan, health | Ej 1 | ⬜ |
| 2 | Modelos, migraciones (auto + trigger a mano), seed.py | Ej 2, 7 | ⬜ |
| 3 | BaseRepository, SoftDelete, UoW, paginación | Ej 6 | ⬜ |
| 4 | Auth y autorización (bcrypt, login, cookie, roles, grupos de rutas) | Ej 4, 5 | ⬜ |
| 5 | Clientes, vehículos y repuestos (stock en un único punto, historial de precios) | Ej 3 | ⬜ |
| 6 | Órdenes: alta, transiciones, terminar, cancelar, sin N+1, aviso | Ej 6, 8 | ⬜ |
| 7 | test/*.http (C-01 a C-19), solo_agregado.sql, evidencias, README | – | ⬜ |

## Decisiones tomadas
- 30/10 · Guía única: el enunciado de 22 páginas. El material de la cátedra no tiene las secciones que cita el TP.
- 30/10 · PostgreSQL 16 instalado nativo en Windows. El enunciado pide PostgreSQL 16 y no pide Docker. `psql` viene incluido y se necesita para la evidencia del caso C-14.
- 30/10 · Python 3.14. Si asyncpg no instala, se usa psycopg 3 async (el enunciado lo acepta).
- 30/10 · Roles de cada IA: Claude Code (VS Code) escribe y prueba el código; el chat de claude.ai planifica, explica y revisa; Gemini extrae y resume el material y hace tareas sueltas que Claude revisa. **Una sola IA escribe código.**

## Registro
### 30/10 · Fase 0
- Plan maestro definido. Se crearon CLAUDE.md y esta bitácora.
- Pendiente: crear la carpeta del proyecto, instalar PostgreSQL 16, crear el repo.

## Próximo paso
Instalar PostgreSQL 16 y crear la carpeta del proyecto con `docs/`.
