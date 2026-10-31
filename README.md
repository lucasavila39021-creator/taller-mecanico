# Taller Mecánico

API para el trabajo diario de un taller mecánico: clientes, vehículos, repuestos, órdenes de trabajo y sus usuarios y roles.
Trabajo práctico de Programación III, Tecnicatura Universitaria en Programación, UTN.

**Grupo:** LucasAvila
**Integrante:** Lucas Avila

## Requisitos

- Python 3.12 o superior (se desarrolló con 3.14).
- PostgreSQL 16 o superior (se desarrolló con 17), instalado en Windows.
- Visual Studio Code con la extensión REST Client, para correr los casos de prueba.

## Puesta en marcha desde cero

Todos los comandos van en la **cmd de Windows**, desde la carpeta del proyecto.

**1. Entorno virtual y dependencias**

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**2. Base de datos**

Si `psql` no está en el PATH, usá la ruta completa de tu instalación. Pide la contraseña de `postgres`.

```
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -c "CREATE DATABASE taller;"
```

**3. Archivo `.env`**

```
copy env.example .env
```

Generá la clave de firma de los tokens:

```
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Abrí `.env` y completá `SECRET_KEY` con esa clave y `POSTGRES_PASSWORD` con la contraseña de tu PostgreSQL. Sin estos dos valores la aplicación no arranca. El archivo `.env` no se sube al repositorio.

**4. Esquema y datos iniciales**

```
alembic upgrade head
python seed.py
```

`seed.py` vacía las tablas y carga el estado inicial que usan los casos de prueba. Es parte de la puesta en marcha: sin el catálogo de estados no se puede crear ninguna orden.

**5. Servidor**

```
uvicorn main:app
```

La API queda en `http://127.0.0.1:8000`, y su documentación interactiva, en `http://127.0.0.1:8000/docs`. Para comprobar que está lista:

```
curl -i http://127.0.0.1:8000/health/ready
```

## Usuarios de prueba

Los carga `seed.py`, todos con la contraseña de mentira `Taller2026!`, que no es una credencial real.

| Correo | Rol | Nota |
|---|---|---|
| `admin@example.com`, `admin2@example.com` | ADMIN | |
| `recepcion@example.com` | RECEPCION | |
| `mecanico@example.com`, `mecanico2@example.com` | MECANICO | |
| `cliente@example.com` | CLIENTE | Laura, con dos vehículos |
| `nuevo@example.com` | MECANICO | Con el cambio de contraseña obligatorio |

## Casos de prueba

### Archivos `.http` (extensión REST Client)

| Archivo | Casos |
|---|---|
| `test/01_autenticacion.http` | C-01 a C-05 |
| `test/02_autorizacion.http` | C-06 a C-09 |
| `test/03_ordenes.http` | C-10 a C-13, C-15 y C-17 |
| `test/04_catalogo.http` | C-16, C-18 y C-19 |

Para cada archivo:

1. Con el servidor levantado, corré `python seed.py` en una cmd con el entorno virtual activado.
2. Abrí el archivo en VS Code y hacé clic en **Send Request**, en cada pedido, **de arriba hacia abajo**: los pedidos usan las sesiones y las órdenes de los anteriores.
3. Compará con la respuesta esperada, que está en el comentario de cada pedido.

### Archivo `.sql` (caso C-14)

Demuestra el disparador de sólo agregado por fuera de la API. Las siete sentencias tienen que terminar en `ERROR`.

```
python seed.py
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -d taller -f test\solo_agregado.sql
```

### Ver las consultas en la consola (caso C-15)

```
set SQL_ECHO=true
uvicorn main:app
```

El detalle de una orden usa la misma cantidad de consultas con 2 y con 4 ítems.

## Entrega

La entrega es un archivo `LucasAvila.zip`, que incluye la carpeta `.git` con el historial de commits.

Se arma desde un clon nuevo del repositorio. Así trae `.git` y sólo lo commiteado: no incluye `.env`, que tiene las credenciales reales, ni `.venv`, que cada uno crea en su PC. Los comandos van en la cmd de Windows:

```
git clone https://github.com/lucasavila39021-creator/taller-mecanico.git "%TEMP%\LucasAvila"
cd /d "%TEMP%\LucasAvila"
tar -a -c -f "%USERPROFILE%\proyectos\LucasAvila.zip" .
cd /d "%USERPROFILE%\proyectos"
rmdir /s /q "%TEMP%\LucasAvila"
```

## Decisiones

- **Capas:** Router → Service → Unit of Work → Repository → Model. El router construye el Unit of Work con una dependencia, y el servicio lo abre. Los repositorios hacen `flush()`, nunca `commit()`.
- **Unicidad:** la garantiza la base, sin consulta previa. El `IntegrityError` se traduce por el nombre de la restricción a un 409 con mensaje propio.
- **`intento_acceso`:** se escribe en una sesión y transacción propias, porque el fallo que se quiere contar es el mismo que revierte la transacción de la petición. Es la única escritura con esta excepción.
- **`seed.py` vacía con `TRUNCATE ... RESTART IDENTITY`:** el disparador rechaza los `DELETE` en las tablas de sólo agregado, y los casos de prueba usan ids fijos.
- **`otorgada_por` es clave foránea a `usuario`:** el enunciado aclara cuando una columna es texto, como `actor`. Es nula cuando no la otorgó un usuario, como en el auto-registro.
- **Correo, patente y código se normalizan:** el correo se guarda en minúsculas; la patente y el código, en mayúsculas. Así `ac456ef` choca con `AC456EF`.
- **Terminar una orden:** el permiso se evalúa antes que el estado, igual que RN-12 para cancelar. Un repuesto dado de baja después del alta igual se descuenta, porque RN-16 sólo prohíbe usarlo en órdenes nuevas.
- **Listados:** `GET /ordenes` y `GET /mis-ordenes` devuelven un resumen, sin ítems ni historial. El detalle completo está en `GET /ordenes/{id}`.
- **Contraseñas en los `.http`:** el enunciado dice que viven sólo en `seed.py`, pero los logins de los casos de prueba necesitan escribirla. Por eso cada archivo declara la misma contraseña de mentira en una variable, con un comentario que lo aclara.
