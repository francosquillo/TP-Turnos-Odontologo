"""008 obras sociales, aranceles y liquidaciones (C-11, D-01, D-03, D-05, D-07..D-09, D-14).

Crea `obra_social`, `plan`, `arancel` (con EXCLUDE sobre `daterange`), `liquidacion` e
`item_liquidacion`. Altera `paciente` (plan), `presupuesto` (plan congelado),
`item_presupuesto` (arancel y cubierto congelados), `movimiento` (indice unico del ajuste de
cobertura) y `movimiento_caja` (`recibo_id` nulable, `liquidacion_id`, una sola referencia).
Repite a proposito los literales de los modelos (la migracion no importa modelos) y un test
los compara. `ALTER TABLE` no dispara los triggers de fila de `movimiento` ni de
`movimiento_caja`.
Reversible: el downgrade falla si hay ingresos de liquidacion, porque `recibo_id` no puede
volver a NOT NULL y `movimiento_caja` es inmutable; se prefiere el error a perder datos.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_obras_sociales"
down_revision: Union[str, None] = "007_caja_recibos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ESTADOS_LIQUIDACION = ("borrador", "presentada", "cobrada")


def _id():
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def _created_at():
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    estados_sql = ", ".join(f"'{e}'" for e in ESTADOS_LIQUIDACION)

    op.create_table(
        "obra_social",
        _id(),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("activa", sa.Boolean(), server_default=sa.true(), nullable=False),
        _created_at(),
        sa.CheckConstraint("length(nombre) BETWEEN 1 AND 120", name="ck_obra_social_nombre_len"),
        sa.UniqueConstraint("nombre", name="uq_obra_social_nombre"),
    )
    op.create_table(
        "plan",
        _id(),
        sa.Column("obra_social_id", sa.BigInteger(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        _created_at(),
        sa.CheckConstraint("length(nombre) BETWEEN 1 AND 120", name="ck_plan_nombre_len"),
        sa.UniqueConstraint("obra_social_id", "nombre", name="uq_plan_obra_social_nombre"),
        sa.ForeignKeyConstraint(["obra_social_id"], ["obra_social.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "arancel",
        _id(),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("codigo_nomenclador", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("precio", sa.Numeric(12, 2), nullable=False),
        sa.Column("vigencia_desde", sa.Date(), nullable=False),
        sa.Column("vigencia_hasta", sa.Date(), nullable=True),
        sa.Column("creado_por", sa.BigInteger(), nullable=True),
        sa.Column("cerrado_por", sa.BigInteger(), nullable=True),
        sa.Column("cerrado_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint("precio > 0", name="ck_arancel_precio_positivo"),
        sa.CheckConstraint(
            "vigencia_hasta IS NULL OR vigencia_hasta >= vigencia_desde",
            name="ck_arancel_vigencia_rango",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cerrado_por"], ["usuario.id"], ondelete="RESTRICT"),
    )
    # D-08: dos versiones del mismo plan y codigo no superponen vigencias (requiere btree_gist, C-01).
    op.execute(
        "ALTER TABLE arancel ADD CONSTRAINT ex_arancel_sin_solape "
        "EXCLUDE USING gist (plan_id WITH =, codigo_nomenclador WITH =, "
        "daterange(vigencia_desde, vigencia_hasta, '[]') WITH &&)"
    )
    op.create_index("ix_arancel_plan_codigo", "arancel", ["plan_id", "codigo_nomenclador"])
    op.create_index("ix_arancel_creado_por", "arancel", ["creado_por"])
    op.create_index("ix_arancel_cerrado_por", "arancel", ["cerrado_por"])

    op.create_table(
        "liquidacion",
        _id(),
        sa.Column("os_id", sa.BigInteger(), nullable=False),
        sa.Column("periodo", sa.Date(), nullable=False),
        sa.Column("estado", sa.Text(), server_default="borrador", nullable=False),
        sa.Column("total", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("creada_por", sa.BigInteger(), nullable=False),
        sa.Column("presentada_por", sa.BigInteger(), nullable=True),
        sa.Column("presentada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cobrada_por", sa.BigInteger(), nullable=True),
        sa.Column("cobrada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cobro_revertido_por", sa.BigInteger(), nullable=True),
        sa.Column("cobro_revertido_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint(f"estado IN ({estados_sql})", name="ck_liquidacion_estado"),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM periodo) = 1", name="ck_liquidacion_periodo_dia_uno"
        ),
        sa.CheckConstraint("total >= 0", name="ck_liquidacion_total_no_negativo"),
        sa.ForeignKeyConstraint(["os_id"], ["obra_social.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creada_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["presentada_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cobrada_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cobro_revertido_por"], ["usuario.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_liquidacion_os_periodo", "liquidacion", ["os_id", "periodo"])
    op.create_index("ix_liquidacion_creada_por", "liquidacion", ["creada_por"])
    op.create_index("ix_liquidacion_presentada_por", "liquidacion", ["presentada_por"])
    op.create_index("ix_liquidacion_cobrada_por", "liquidacion", ["cobrada_por"])
    op.create_index("ix_liquidacion_cobro_revertido_por", "liquidacion", ["cobro_revertido_por"])

    op.create_table(
        "item_liquidacion",
        _id(),
        sa.Column("liquidacion_id", sa.BigInteger(), nullable=False),
        sa.Column("item_presupuesto_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("arancel_id", sa.BigInteger(), nullable=True),
        sa.Column("fecha_prestacion", sa.Date(), nullable=False),
        sa.Column("monto", sa.Numeric(16, 2), nullable=False),
        sa.CheckConstraint("monto >= 0", name="ck_itemliq_monto_no_negativo"),
        sa.CheckConstraint(
            "arancel_id IS NOT NULL OR monto = 0", name="ck_itemliq_revision_monto_cero"
        ),
        sa.UniqueConstraint("item_presupuesto_id", name="uq_itemliq_item_presupuesto"),
        sa.ForeignKeyConstraint(["liquidacion_id"], ["liquidacion.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["item_presupuesto_id"], ["item_presupuesto.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["arancel_id"], ["arancel.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_itemliq_liquidacion_id", "item_liquidacion", ["liquidacion_id"])
    op.create_index("ix_itemliq_plan_id", "item_liquidacion", ["plan_id"])
    op.create_index("ix_itemliq_arancel_id", "item_liquidacion", ["arancel_id"])

    # D-07 / D-03: plan del paciente, plan congelado, arancel y cubierto congelados.
    op.add_column("paciente", sa.Column("plan_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "paciente_plan_id_fkey", "paciente", "plan", ["plan_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_paciente_plan_id", "paciente", ["plan_id"])
    op.add_column("presupuesto", sa.Column("plan_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "presupuesto_plan_id_fkey", "presupuesto", "plan", ["plan_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_presupuesto_plan_id", "presupuesto", ["plan_id"])
    op.add_column("item_presupuesto", sa.Column("arancel_id", sa.BigInteger(), nullable=True))
    op.add_column("item_presupuesto", sa.Column("cubierto", sa.Numeric(16, 2), nullable=True))
    op.create_foreign_key(
        "item_presupuesto_arancel_id_fkey", "item_presupuesto", "arancel", ["arancel_id"],
        ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_item_presupuesto_arancel_id", "item_presupuesto", ["arancel_id"])
    op.create_check_constraint(
        "ck_item_cubierto_no_negativo", "item_presupuesto",
        "cubierto IS NULL OR cubierto >= 0",
    )

    # D-05: como mucho un ajuste de cobertura por presupuesto.
    op.create_index(
        "uq_movimiento_cobertura_presupuesto", "movimiento", ["presupuesto_id"],
        unique=True,
        postgresql_where=sa.text(
            "tipo = 'ajuste' AND anula_a_id IS NULL AND recibo_id IS NULL AND monto < 0"
        ),
    )

    # D-14: el movimiento de caja referencia un recibo o una liquidacion, nunca ambos ni ninguno.
    op.alter_column("movimiento_caja", "recibo_id", existing_type=sa.BigInteger(), nullable=True)
    op.add_column("movimiento_caja", sa.Column("liquidacion_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "movimiento_caja_liquidacion_id_fkey", "movimiento_caja", "liquidacion",
        ["liquidacion_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_movcaja_una_referencia", "movimiento_caja",
        "num_nonnulls(recibo_id, liquidacion_id) = 1",
    )
    op.create_index("ix_movcaja_liquidacion_id", "movimiento_caja", ["liquidacion_id"])
    op.create_index(
        "uq_movcaja_liq_ingreso", "movimiento_caja", ["liquidacion_id"],
        unique=True, postgresql_where=sa.text("monto > 0"),
    )
    op.create_index(
        "uq_movcaja_liq_reversion", "movimiento_caja", ["liquidacion_id"],
        unique=True, postgresql_where=sa.text("monto < 0"),
    )


def downgrade() -> None:
    # `movimiento_caja` es inmutable: con ingresos de liquidacion no hay vuelta atras limpia.
    hay_ingresos = op.get_bind().execute(
        sa.text("SELECT 1 FROM movimiento_caja WHERE liquidacion_id IS NOT NULL LIMIT 1")
    ).first()
    if hay_ingresos is not None:
        raise RuntimeError(
            "no se puede revertir 008: hay movimientos de caja de liquidaciones"
        )
    op.execute("DROP INDEX IF EXISTS uq_movcaja_liq_reversion")
    op.execute("DROP INDEX IF EXISTS uq_movcaja_liq_ingreso")
    op.execute("DROP INDEX IF EXISTS ix_movcaja_liquidacion_id")
    op.drop_constraint("ck_movcaja_una_referencia", "movimiento_caja", type_="check")
    op.drop_constraint(
        "movimiento_caja_liquidacion_id_fkey", "movimiento_caja", type_="foreignkey"
    )
    op.drop_column("movimiento_caja", "liquidacion_id")
    op.alter_column("movimiento_caja", "recibo_id", existing_type=sa.BigInteger(), nullable=False)

    op.execute("DROP INDEX IF EXISTS uq_movimiento_cobertura_presupuesto")

    op.drop_constraint("ck_item_cubierto_no_negativo", "item_presupuesto", type_="check")
    op.execute("DROP INDEX IF EXISTS ix_item_presupuesto_arancel_id")
    op.drop_constraint(
        "item_presupuesto_arancel_id_fkey", "item_presupuesto", type_="foreignkey"
    )
    op.drop_column("item_presupuesto", "cubierto")
    op.drop_column("item_presupuesto", "arancel_id")
    op.execute("DROP INDEX IF EXISTS ix_presupuesto_plan_id")
    op.drop_constraint("presupuesto_plan_id_fkey", "presupuesto", type_="foreignkey")
    op.drop_column("presupuesto", "plan_id")
    op.execute("DROP INDEX IF EXISTS ix_paciente_plan_id")
    op.drop_constraint("paciente_plan_id_fkey", "paciente", type_="foreignkey")
    op.drop_column("paciente", "plan_id")

    op.execute("DROP TABLE IF EXISTS item_liquidacion")
    op.execute("DROP TABLE IF EXISTS liquidacion")
    op.execute("DROP TABLE IF EXISTS arancel")
    op.execute("DROP TABLE IF EXISTS plan")
    op.execute("DROP TABLE IF EXISTS obra_social")
