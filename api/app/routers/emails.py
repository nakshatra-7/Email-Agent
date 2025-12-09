from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..database import get_session
from ..models import Email, EmailCreate, EmailStatus, EmailUpdate

router = APIRouter(prefix="/emails", tags=["emails"])


@router.post(
    "/",
    response_model=Email,
    status_code=status.HTTP_201_CREATED,
    summary="Create an email entry",
)
def create_email(payload: EmailCreate, session: Session = Depends(get_session)) -> Email:
    email = Email(**payload.dict())
    session.add(email)
    session.commit()
    session.refresh(email)
    return email


@router.get(
    "/",
    response_model=List[Email],
    summary="List emails with optional status filter",
)
def list_emails(
    status: Optional[EmailStatus] = None, session: Session = Depends(get_session)
) -> List[Email]:
    statement = select(Email)
    if status:
        statement = statement.where(Email.status == status)
    statement = statement.order_by(Email.created_at.desc())
    emails = session.exec(statement).all()
    return emails


@router.get(
    "/{email_id}",
    response_model=Email,
    summary="Fetch a single email",
)
def get_email(email_id: int, session: Session = Depends(get_session)) -> Email:
    email = session.get(Email, email_id)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Email not found"
        )
    return email


@router.patch(
    "/{email_id}",
    response_model=Email,
    summary="Update fields of an email",
)
def update_email(
    email_id: int, payload: EmailUpdate, session: Session = Depends(get_session)
) -> Email:
    email = session.get(Email, email_id)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Email not found"
        )

    update_data = payload.dict(exclude_unset=True)
    if not update_data:
        return email

    for key, value in update_data.items():
        setattr(email, key, value)
    email.updated_at = datetime.utcnow()

    session.add(email)
    session.commit()
    session.refresh(email)
    return email


@router.delete(
    "/{email_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an email",
)
def delete_email(email_id: int, session: Session = Depends(get_session)) -> None:
    email = session.get(Email, email_id)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Email not found"
        )
    session.delete(email)
    session.commit()
