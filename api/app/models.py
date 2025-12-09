from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class EmailStatus(str, Enum):
    draft = "draft"
    queued = "queued"
    sent = "sent"
    failed = "failed"


class EmailBase(SQLModel):
    subject: str = Field(index=True, max_length=200)
    body: str
    from_address: str = Field(max_length=320, description="Sender email address")
    to_address: str = Field(max_length=320, description="Recipient email address")
    status: EmailStatus = Field(default=EmailStatus.draft)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    attachments: List[dict] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="List of attachment metadata (filename, mimeType, size, gmail_id)",
    )
    intent_analysis: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="LLM-provided intent analysis payload",
    )
    intent_actions: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Derived actions based on intent analysis",
    )
    processed: bool = Field(
        default=False,
        description="Whether this email has been fully processed by the agent",
        index=True,
    )


class Email(EmailBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    gmail_id: Optional[str] = Field(
        default=None, index=True, description="Gmail message id for synced email"
    )
    thread_id: Optional[str] = Field(
        default=None, index=True, description="Gmail thread id"
    )
    snippet: Optional[str] = Field(default=None, description="Short preview")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = Field(
        default=None, description="When the agent finished processing this email"
    )


class EmailCreate(EmailBase):
    pass


class EmailUpdate(SQLModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[EmailStatus] = None
    tags: Optional[List[str]] = None
