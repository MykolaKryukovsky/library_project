from ninja import Schema
from typing import Optional


class BookIn(Schema):
    title: str
    author: str
    genre: str
    available_copies: int = 1


class BookOut(Schema):
    id: int
    title: str
    author: str
    genre: str
    available_copies: int


class QueueResponse(Schema):
    status: str
    message: str
