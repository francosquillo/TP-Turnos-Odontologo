"""005 clinica: historia clinica + odontograma + catalogos (C-08, D-01..D-06, D-10).

Corrige "Migracion 003" de CHANGES.md: la cabeza previa es 004_espera.
Carga el catalogo de estados V1 (bulk_insert) para que exista sin seed; repite
los literales de `CATALOGO_ESTADOS_V1` a proposito (la migracion no importa
modelos) y un test compara ambos.
Reversible: downgrade elimina tablas e indices (solo datos ficticios).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_clinica"
down_revision: Union[str, None] = "004_espera"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VERSION_V1 = 1
CATALOGO_V1 = (
    ("sano", "Sano", "cualquiera"),
    ("caries", "Caries", "cualquiera"),
    ("obturacion", "Obturación", "cualquiera"),
    ("corona", "Corona", "pieza"),
    ("endodoncia", "Endodoncia", "pieza"),
    ("implante", "Implante", "pieza"),
    ("ausente", "Ausente", "pieza"),
)
CARAS = (
    "oclusal", "mesial", "distal", "vestibular", "palatina", "lingual",
    "raiz", "pieza_completa",
)


def upgrade() -> None:
    catalogo = op.create_table(
        "estado_hallazgo_catalogo",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("version", sa.SmallInteger(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("alcance", sa.Text(), nullable=False),
        sa.Column("vigente", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("codigo", "version", name="uq_estado_catalogo_codigo_version"),
        sa.CheckConstraint(
            "alcance IN ('cualquiera', 'pieza')", name="ck_estado_catalogo_alcance"
        ),
    )
    op.bulk_insert(
        catalogo,
        [
            {"codigo": c, "version": VERSION_V1, "nombre": n, "alcance": a, "vigente": True}
            for c, n, a in CATALOGO_V1
        ],
    )

    op.create_table(
        "tratamiento",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("codigo", sa.Text(), nullable=False, unique=True),
        sa.Column("codigo_nomenclador", sa.Text(), nullable=True),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("precio_base", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint("precio_base >= 0", name="ck_tratamiento_precio_no_negativo"),
    )

    op.create_table(
        "historia_clinica",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("antecedentes", sa.Text(), nullable=True),
        sa.Column("alergias", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_baja", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "(deleted_at IS NULL) = (motivo_baja IS NULL)", name="ck_hc_baja_con_motivo"
        ),
        sa.CheckConstraint(
            "antecedentes IS NULL OR length(antecedentes) <= 10000",
            name="ck_hc_antecedentes_largo",
        ),
        sa.CheckConstraint(
            "alergias IS NULL OR length(alergias) <= 2000", name="ck_hc_alergias_largo"
        ),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.id"], ondelete="RESTRICT"),
    )

    caras_sql = ", ".join(f"'{c}'" for c in CARAS)
    op.create_table(
        "hallazgo_odontograma",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("hc_id", sa.BigInteger(), nullable=False),
        sa.Column("pieza_fdi", sa.SmallInteger(), nullable=False),
        sa.Column("cara", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("catalogo_version", sa.SmallInteger(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=False),
        sa.Column("corrige_a_id", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_baja", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "pieza_fdi BETWEEN 11 AND 48 AND pieza_fdi % 10 BETWEEN 1 AND 8",
            name="ck_hallazgo_pieza_fdi_valida",
        ),
        sa.CheckConstraint(f"cara IN ({caras_sql})", name="ck_hallazgo_cara_catalogo"),
        sa.CheckConstraint(
            "(cara <> 'palatina' OR pieza_fdi < 30) AND "
            "(cara <> 'lingual' OR pieza_fdi >= 30)",
            name="ck_hallazgo_cara_arcada",
        ),
        sa.CheckConstraint(
            "(deleted_at IS NULL) = (motivo_baja IS NULL)",
            name="ck_hallazgo_baja_con_motivo",
        ),
        sa.ForeignKeyConstraint(
            ["estado", "catalogo_version"],
            ["estado_hallazgo_catalogo.codigo", "estado_hallazgo_catalogo.version"],
            name="fk_hallazgo_estado_catalogo",
        ),
        sa.ForeignKeyConstraint(["hc_id"], ["historia_clinica.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["profesional_id"], ["profesional.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["corrige_a_id"], ["hallazgo_odontograma.id"]),
    )
    op.create_index("ix_hallazgo_hc_pieza", "hallazgo_odontograma", ["hc_id", "pieza_fdi"])
    op.create_index("ix_hallazgo_profesional_id", "hallazgo_odontograma", ["profesional_id"])
    op.create_index(
        "ix_hallazgo_estado_version", "hallazgo_odontograma", ["estado", "catalogo_version"]
    )
    op.create_index(
        "uq_hallazgo_corrige_a",
        "hallazgo_odontograma",
        ["corrige_a_id"],
        unique=True,
        postgresql_where=sa.text("corrige_a_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_hallazgo_corrige_a")
    op.execute("DROP INDEX IF EXISTS ix_hallazgo_estado_version")
    op.execute("DROP INDEX IF EXISTS ix_hallazgo_profesional_id")
    op.execute("DROP INDEX IF EXISTS ix_hallazgo_hc_pieza")
    op.execute("DROP TABLE IF EXISTS hallazgo_odontograma")
    op.execute("DROP TABLE IF EXISTS historia_clinica")
    op.execute("DROP TABLE IF EXISTS tratamiento")
    op.execute("DROP TABLE IF EXISTS estado_hallazgo_catalogo")
