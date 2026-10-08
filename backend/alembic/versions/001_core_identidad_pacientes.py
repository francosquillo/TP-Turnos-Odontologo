"""001 core identidad pacientes: Rol/Usuario/Paciente/Profesional/Sillon (C-02).

Convenciones D-05: PK BIGINT GENERATED ALWAYS AS IDENTITY, TIMESTAMPTZ,
TEXT+CHECK, JSONB+GIN, unique parcial DNI, LOWER(email) unico, indice por FK.
Reversible: downgrade elimina las 5 tablas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001_core_identidad_pacientes"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rol",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "nombre IN ('admin', 'odontologo', 'secretaria')",
            name="ck_rol_nombre_catalogo",
        ),
        sa.CheckConstraint("length(nombre) <= 32", name="ck_rol_nombre_len"),
        sa.UniqueConstraint("nombre", name="uq_rol_nombre"),
    )
    op.create_table(
        "usuario",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("rol_id", sa.BigInteger(), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(nombre) <= 120", name="ck_usuario_nombre_len"),
        sa.CheckConstraint("length(email) <= 320", name="ck_usuario_email_len"),
        sa.ForeignKeyConstraint(["rol_id"], ["rol.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("email", name="uq_usuario_email"),
    )
    op.create_index("ix_usuario_rol_id", "usuario", ["rol_id"])
    op.create_index(
        "uq_usuario_email_lower", "usuario", [sa.text("lower(email)")], unique=True
    )
    op.create_table(
        "paciente",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("apellido", sa.Text(), nullable=False),
        sa.Column("dni", sa.Text(), nullable=True),
        sa.Column("telefono", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("cobertura_os", sa.Text(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column(
            "consentimiento_datos",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("consentimiento_fecha", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(nombre) <= 120", name="ck_paciente_nombre_len"),
        sa.CheckConstraint("length(apellido) <= 120", name="ck_paciente_apellido_len"),
        sa.CheckConstraint("length(dni) <= 20", name="ck_paciente_dni_len"),
    )
    op.create_index(
        "uq_paciente_dni",
        "paciente",
        ["dni"],
        unique=True,
        postgresql_where=sa.text("dni IS NOT NULL"),
    )
    op.create_index("ix_paciente_apellido", "paciente", ["apellido"])
    op.create_index("ix_paciente_telefono", "paciente", ["telefono"])
    op.create_table(
        "profesional",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("usuario_id", sa.BigInteger(), nullable=True),
        sa.Column("matricula", sa.Text(), nullable=False),
        sa.Column("especialidades", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "agenda_config",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(matricula) <= 40", name="ck_profesional_matricula_len"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("matricula", name="uq_profesional_matricula"),
    )
    op.create_index("ix_profesional_usuario_id", "profesional", ["usuario_id"])
    op.create_index(
        "ix_profesional_agenda_gin",
        "profesional",
        ["agenda_config"],
        postgresql_using="gin",
    )
    op.create_table(
        "sillon",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column(
            "sede", sa.Text(), server_default=sa.text("'Sede única'"), nullable=False
        ),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(nombre) <= 80", name="ck_sillon_nombre_len"),
        sa.UniqueConstraint("nombre", name="uq_sillon_nombre"),
    )


def downgrade() -> None:
    op.drop_table("sillon")
    op.drop_index("ix_profesional_agenda_gin", table_name="profesional")
    op.drop_index("ix_profesional_usuario_id", table_name="profesional")
    op.drop_table("profesional")
    op.drop_index("ix_paciente_telefono", table_name="paciente")
    op.drop_index("ix_paciente_apellido", table_name="paciente")
    op.drop_index("uq_paciente_dni", table_name="paciente")
    op.drop_table("paciente")
    op.drop_index("uq_usuario_email_lower", table_name="usuario")
    op.drop_index("ix_usuario_rol_id", table_name="usuario")
    op.drop_table("usuario")
    op.drop_table("rol")
