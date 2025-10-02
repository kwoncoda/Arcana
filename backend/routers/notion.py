"""Notion OAuth 및 페이지 조회 라우터."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from utils.db import get_db

router = APIRouter(tags=["notion"])