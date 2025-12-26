"""FastAPI dependencies for wishes module."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.wishes.service import WishService


def get_wish_service(db: Session = Depends(get_db)) -> WishService:
    return WishService(db)


WishServiceDep = Annotated[WishService, Depends(get_wish_service)]
