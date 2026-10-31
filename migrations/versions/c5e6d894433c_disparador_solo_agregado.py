"""disparador solo agregado

Revision ID: c5e6d894433c
Revises: 2055df82434f
Create Date: 2026-10-30 22:47:01.002084

"""
# Escrita a mano y revisada antes de aplicarla: autogenerate no ve funciones ni disparadores.
# RN-15: una función y tres disparadores que rechazan todo UPDATE o DELETE, venga de donde venga.
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c5e6d894433c'
down_revision: Union[str, Sequence[str], None] = '2055df82434f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLAS_SOLO_AGREGADO = ("historial_estado_orden", "movimiento_stock", "historial_precio_repuesto")


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE FUNCTION rechazar_modificacion_solo_agregado() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'La tabla % es de sólo agregado: no se permite %', TG_TABLE_NAME, TG_OP;
        END;
        $$
        """
    )
    # Un op.execute por sentencia: asyncpg no acepta varias sentencias en una sola llamada.
    for tabla in TABLAS_SOLO_AGREGADO:
        op.execute(
            f"""
            CREATE TRIGGER trg_solo_agregado_{tabla}
            BEFORE UPDATE OR DELETE ON {tabla}
            FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion_solo_agregado()
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Primero los disparadores, porque dependen de la función.
    for tabla in TABLAS_SOLO_AGREGADO:
        op.execute(f"DROP TRIGGER trg_solo_agregado_{tabla} ON {tabla}")
    op.execute("DROP FUNCTION rechazar_modificacion_solo_agregado()")
