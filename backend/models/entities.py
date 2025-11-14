"""SQLAlchemy ORM models shared across backend modules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    String,
    Boolean,
    Text,
    JSON,
    Integer,
    UniqueConstraint,
    text,
)

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


class User(Base):
    """유저 엔티티"""
    __tablename__ = "users"

    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    id = Column(String(255), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    nickname = Column(String(100), unique=True)
    password_hash = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime)


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


class RagIndex(Base):
    """워크스페이스별 RAG 인덱스 메타데이터."""

    __tablename__ = "rag_indexes"

    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_idx = Column(BigInteger, nullable=False)
    name = Column(String(200), nullable=False, default="default")
    index_type = Column(String(20), nullable=False)
    storage_uri = Column(String(1000), nullable=False)
    dim = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="ready")
    object_count = Column(Integer, nullable=False, default=0)
    vector_count = Column(Integer, nullable=False, default=0)
    updated = Column(DateTime, nullable=False, server_default=text("'1970-01-01 00:00:00'"))

class NotionOauthCredentials(Base):
    __tablename__ = "notion_oauth_credentials"

    idx                   = Column(BigInteger, primary_key=True, autoincrement=True)
    user_idx              = Column(BigInteger, nullable=False)         # FK: users.idx
    data_source_idx       = Column(BigInteger, nullable=False)         # FK: data_sources.idx
    provider              = Column(String(50), nullable=False, default="notion")
    bot_id                = Column(String(100), nullable=False)
    provider_workspace_id = Column(String(64), nullable=True)          # Notion workspace_id
    workspace_name        = Column(String(255), nullable=True)
    workspace_icon        = Column(String(1000), nullable=True)
    token_type            = Column(String(20), nullable=False, default="bearer")
    access_token          = Column(Text, nullable=False)
    refresh_token         = Column(Text, nullable=True)
    expires               = Column(DateTime, nullable=True)            # MySQL DATETIME (naive)
    created               = Column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    updated               = Column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    provider_payload      = Column(JSON, nullable=True)

class DataSource(Base):
    __tablename__ = "data_sources"
    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    workspace_idx = Column(BigInteger, nullable=False)  # FK: workspaces.idx
    type = Column(String(20), nullable=False)           # 'notion', 'googledrive', 'local'
    name = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="connected")  # connected/disconnected/error
    synced = Column(DateTime, nullable=True)
    created = Column(DateTime, nullable=False, default=datetime.utcnow)


class GoogleDriveOauthCredentials(Base):
    __tablename__ = "google_drive_oauth_credentials"

    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    user_idx = Column(BigInteger, nullable=False)          # FK: users.idx
    data_source_idx = Column(BigInteger, nullable=False)   # FK: data_sources.idx
    provider = Column(String(50), nullable=False, default="googledrive")
    google_user_id = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    token_type = Column(String(20), nullable=False, default="Bearer")
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    scope = Column(Text, nullable=True)
    id_token = Column(Text, nullable=True)
    expires = Column(DateTime, nullable=True)
    created = Column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    updated = Column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    provider_payload = Column(JSON, nullable=True)


class GoogleDriveSyncState(Base):
    """Google Drive Changes API 증분 동기화 상태."""

    __tablename__ = "google_drive_sync_state"

    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    data_source_idx = Column(BigInteger, nullable=False, unique=True)
    start_page_token = Column(String(255), nullable=True)
    pending_page_token = Column(String(255), nullable=True)
    latest_history_id = Column(String(255), nullable=True)
    bootstrapped_at = Column(DateTime, nullable=True)
    last_synced = Column(DateTime, nullable=True)
    created = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated = Column(DateTime, nullable=False, default=datetime.utcnow)


class GoogleDriveFileSnapshot(Base):
    """Google Drive에서 인덱싱한 파일 스냅샷."""

    __tablename__ = "google_drive_file_snapshots"

    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    data_source_idx = Column(BigInteger, nullable=False)
    file_id = Column(String(128), nullable=False)
    name = Column(String(1024), nullable=True)
    mime_type = Column(String(255), nullable=False)
    md5_checksum = Column(String(128), nullable=True)
    version = Column(BigInteger, nullable=True)
    modified_time = Column(DateTime, nullable=True)
    web_view_link = Column(String(1024), nullable=True)
    last_synced = Column(DateTime, nullable=False, default=datetime.utcnow)
    created = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("data_source_idx", "file_id", name="uk_google_drive_file"),
    )