from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class HelpPointRow(Base):
    __tablename__ = "help_points"
    __table_args__ = (CheckConstraint("char_length(nombre) between 1 and 120"), CheckConstraint("char_length(descripcion) between 1 and 1000"), CheckConstraint("zonas_adicionales is null or char_length(zonas_adicionales) between 1 and 500", name="help_points_zonas_adicionales_check"), CheckConstraint("categoria in ('Recolección de donaciones', 'Remoción de escombros', 'Labores de rescate')", name="help_points_categoria_check"), CheckConstraint("char_length(nombre_coordinador) between 1 and 120"), CheckConstraint("char_length(contacto_coordinador) between 1 and 240"), CheckConstraint("char_length(admin_token) >= 40"))
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    zonas_adicionales: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enlaces_importantes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)
    nombre_coordinador: Mapped[str] = mapped_column(String(120), nullable=False)
    contacto_coordinador: Mapped[str] = mapped_column(String(240), nullable=False)
    admin_token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    needs: Mapped[list["NeedRow"]] = relationship(back_populates="help_point", cascade="all, delete-orphan")
    locations: Mapped[list["HelpPointLocationRow"]] = relationship(back_populates="help_point", cascade="all, delete-orphan")
    affected_areas: Mapped[list["HelpPointAffectedAreaRow"]] = relationship(back_populates="help_point", cascade="all, delete-orphan")


class HelpPointLocationRow(Base):
    __tablename__ = "help_point_locations"
    __table_args__ = (CheckConstraint("direccion is null or char_length(direccion) between 1 and 240", name="help_point_locations_direccion_check"), CheckConstraint("char_length(ciudad) between 1 and 120", name="help_point_locations_ciudad_check"), CheckConstraint("char_length(departamento) between 1 and 120", name="help_point_locations_departamento_check"), CheckConstraint("latitude between -90 and 90", name="help_point_locations_latitude_check"), CheckConstraint("longitude between -180 and 180", name="help_point_locations_longitude_check"))
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    help_point_id: Mapped[UUID] = mapped_column(ForeignKey("help_points.id", ondelete="CASCADE"), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(240), nullable=True)
    ciudad: Mapped[str] = mapped_column(String(120), nullable=False)
    departamento: Mapped[str] = mapped_column(String(120), nullable=False)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    help_point: Mapped[HelpPointRow] = relationship(back_populates="locations")


class HelpPointAffectedAreaRow(Base):
    __tablename__ = "help_point_affected_areas"
    __table_args__ = (CheckConstraint("char_length(departamento) between 1 and 120", name="help_point_affected_areas_departamento_check"), CheckConstraint("municipio is null or char_length(municipio) between 1 and 120", name="help_point_affected_areas_municipio_check"))
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    help_point_id: Mapped[UUID] = mapped_column(ForeignKey("help_points.id", ondelete="CASCADE"), nullable=False)
    departamento: Mapped[str] = mapped_column(String(120), nullable=False)
    municipio: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    help_point: Mapped[HelpPointRow] = relationship(back_populates="affected_areas")


class NeedCategoryRow(Base):
    __tablename__ = "need_categories"
    __table_args__ = (CheckConstraint("char_length(nombre) between 1 and 120"), CheckConstraint("char_length(grupo) between 1 and 120"))
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    grupo: Mapped[str] = mapped_column(String(120), nullable=False)
    es_global: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    needs: Mapped[list["NeedRow"]] = relationship(back_populates="category")


class NeedRow(Base):
    __tablename__ = "needs"
    __table_args__ = (UniqueConstraint("help_point_id", "category_id"), CheckConstraint("estado in ('NEEDS_HELP', 'HELP_ON_THE_WAY', 'COVERED')"))
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    help_point_id: Mapped[UUID] = mapped_column(ForeignKey("help_points.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("need_categories.id", ondelete="RESTRICT"), nullable=False)
    estado: Mapped[str] = mapped_column(String(32), default="NEEDS_HELP", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    help_point: Mapped[HelpPointRow] = relationship(back_populates="needs")
    category: Mapped[NeedCategoryRow] = relationship(back_populates="needs")
    commitments: Mapped[list["CommitmentRow"]] = relationship(back_populates="need", cascade="all, delete-orphan")


class CommitmentRow(Base):
    __tablename__ = "commitments"
    __table_args__ = (CheckConstraint("char_length(nombre) between 1 and 120"), CheckConstraint("nota is null or char_length(nota) <= 500"))
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    need_id: Mapped[UUID] = mapped_column(ForeignKey("needs.id", ondelete="CASCADE"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    nota: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    need: Mapped[NeedRow] = relationship(back_populates="commitments")
