"""
Dataset and model code package models.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Dataset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Uploaded dataset associated with a project."""

    __tablename__ = "datasets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    format: Mapped[str] = mapped_column(
        String(32),
        default="zip",
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    is_validated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    validation_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="datasets",
    )


class ModelPackage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Uploaded model training code package (tar.gz/zip) with entrypoint and manifest.
    """

    __tablename__ = "model_packages"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    entrypoint: Mapped[str] = mapped_column(
        String(128),
        default="train.py",
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    # Serialized manifest JSON specifying parameters, dependencies, python version
    manifest_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_validated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    validation_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="packages",
    )
