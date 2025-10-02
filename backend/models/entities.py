"""SQLAlchemy ORM models shared across backend modules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime, String

from utils.db import Base


class WorkspaceType(str, Enum):
    """분리된 워크스페이스 유형 정의."""

    personal = "personal"
    organization = "organization"


class Workspace(Base):
    """워크스페이스 메타데이터."""

    __tablename__ = "workspaces"

    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False)
    name = Column(String(200), nullable=False)
    owner_user_idx = Column(BigInteger, nullable=True)
    organization_idx = Column(BigInteger, nullable=True)
    created = Column(DateTime, nullable=False, default=datetime.utcnow)


class Organization(Base):
    """조직 엔터티."""

    __tablename__ = "organizations"

    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    created = Column(DateTime, nullable=False, default=datetime.utcnow)


class Membership(Base):
    """조직-사용자 Membership 관계."""

    __tablename__ = "memberships"

    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_idx = Column(BigInteger, nullable=False)
    user_idx = Column(BigInteger, nullable=False)
    role = Column(String(50), nullable=False, default="member")
    created = Column(DateTime, nullable=False, default=datetime.utcnow)
