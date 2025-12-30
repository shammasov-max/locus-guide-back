"""FastAPI dependencies for purchases module."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db


# Async database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]
