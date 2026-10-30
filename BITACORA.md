# BITÁCORA — TP Taller Mecánico

> El parte de cambio de turno: qué se hizo, qué se decidió y qué sigue.
> Actualizar al cerrar cada fase. Lo más nuevo va arriba en "Registro".

## Estado de fases
| # | Fase | Ejercicios | Estado |
|---|------|-----------|--------|
| 0 | Entorno: PostgreSQL, repo, venv, docs | – | ✅ |
| 1 | Config, database, lifespan, health | Ej 1 | ⬜ |
| 2 | Modelos, migraciones (auto + trigger a mano), seed.py | Ej 2, 7 | ⬜ |
| 3 | BaseRepository, SoftDelete, UoW, paginación | Ej 6 | ⬜ |
| 4 | Auth y autorización (bcrypt, login, cookie, roles, grupos de rutas) | Ej 4, 5 | ⬜ |
| 5 | Clientes, vehículos y repuestos (stock en un único punto, historial de precios) | Ej 3 | ⬜ |
| 6 | Órdenes: alta, transiciones, terminar, cancelar, sin N+1, aviso | Ej 6, 8 | ⬜ |
| 7 | test/*.http (C-01 a C-19), solo_agregado.sql, evidencias, README | – | ⬜ |

## Decisiones tomadas
- 30/10 · Guía única: el enunciado de 22 páginas. El material de la cátedra no tiene las secciones que cita el TP.
- 30/10 · PostgreSQL 17.11 nativo en Windows: ya estaba instalado y cumple el mínimo 16 del enunciado, que no pide Docker. `psql` viene incluido y se necesita para la evidencia del caso C-14.
- 30/10 · Python 3.14. asyncpg 0.32 instaló e importa bien en Python 3.14; la conexión real se prueba en la Fase 1.
- 30/10 · Roles de cada IA: Claude Code (VS Code) escribe y prueba el código; el chat de claude.ai planifica, explica y revisa; Gemini extrae y resume el material y hace tareas sueltas que Claude revisa. **Una sola IA escribe código.**

## Registro
### 30/10 · Fase 0
- Plan maestro definido. Se crearon CLAUDE.md y esta bitácora.
- Repo Git creado (commit 40c6fdd). `.gitignore` con `.env` protegido.
- venv con Python 3.14. `requirements.txt` instalado (SQLAlchemy 2.1.6, SQLModel 0.0.48).

## Próximo paso
Fase 1: config, database, lifespan y health.
