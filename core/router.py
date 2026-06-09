from datetime import timedelta
from typing import List, Optional
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from ninja import Router, Schema
from ninja.errors import HttpError

from .models import Book, Loan, QueueEntry
from .auth import JWTAuth, create_access_token


books_router = Router(tags=["Книги"])
loans_router = Router(tags=["Очередь и Чтение"])
auth_router = Router(tags=["Аутентификация"])


CACHE_TTL = 300


class LoginIn(Schema):
    username: str
    password: str


class TokenOut(Schema):
    access_token: str
    token_type: str = "bearer"


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


@auth_router.post("/login", response=TokenOut)
def login(request, data: LoginIn):
    """Вход в систему для получения JWT-токена"""
    user = authenticate(username=data.username, password=data.password)
    if not user:
        raise HttpError(401, "Неверное имя пользователя или пароль")

    token = create_access_token(user)
    return {"access_token": token}


@books_router.post("/", response=BookOut, auth=JWTAuth())
def create_book(request, data: BookIn):
    if not request.auth.is_staff:
        raise HttpError(403, "У вас нет прав для добавления книг")

    book = Book.objects.create(**data.dict())
    cache.delete_pattern("books_search:*")
    return book


@books_router.get("/", response=List[BookOut])
def list_books(request, title: Optional[str] = None, author: Optional[str] = None, genre: Optional[str] = None):
    cache_key = f"books_search:{title or ''}:{author or ''}:{genre or ''}"
    cached_books = cache.get(cache_key)
    if cached_books:
        return cached_books

    books = Book.objects.all()
    if title: books = books.filter(title__icontains=title)
    if author: books = books.filter(author__icontains=author)
    if genre: books = books.filter(genre__icontains=genre)

    books_list = list(books)
    cache.set(cache_key, books_list, timeout=CACHE_TTL)
    return books_list


@books_router.get("/{book_id}", response=BookOut)
def get_book(request, book_id: int):
    return get_object_or_404(Book, id=book_id)


@books_router.put("/{book_id}", response=BookOut, auth=JWTAuth())
def update_book(request, book_id: int, data: BookIn):
    if not request.auth.is_staff:
        raise HttpError(403, "У вас нет прав для редактирования")

    book = get_object_or_404(Book, id=book_id)
    for attr, value in data.dict().items():
        setattr(book, attr, value)
    book.save()
    cache.delete_pattern("books_search:*")
    return book


@books_router.delete("/{book_id}", auth=JWTAuth())
def delete_book(request, book_id: int):
    if not request.auth.is_staff:
        raise HttpError(403, "У вас нет прав для удаления")

    book = get_object_or_404(Book, id=book_id)
    book.delete()
    cache.delete_pattern("books_search:*")
    return {"success": True, "message": "Книга успешно удалена"}


@loans_router.post("/{book_id}/borrow", response=QueueResponse, auth=JWTAuth())
def borrow_or_queue_book(request, book_id: int):
    """Взять книгу на 1 час (ID пользователя безопасно берется из JWT токена)"""
    book = get_object_or_404(Book, id=book_id)
    user = request.auth

    if Loan.objects.filter(book=book, user=user, returned=False).exists():
        return {"status": "error", "message": "Вы уже читаете эту книгу в данный момент."}

    if book.available_copies > 0:
        return_time = timezone.now() + timedelta(hours=1)
        Loan.objects.create(book=book, user=user, return_by=return_time)

        book.available_copies -= 1
        book.save()
        return {
            "status": "borrowed",
            "message": f"Книга ваша! Время на чтение: 1 час. Вернуть до: {return_time.strftime('%H:%M:%S')}"
        }

    if QueueEntry.objects.filter(book=book, user=user, status='waiting').exists():
        return {"status": "error", "message": "Вы уже находитесь в очереди на эту книгу."}

    QueueEntry.objects.create(book=book, user=user)
    return {"status": "queued", "message": "Все копии заняты. Вы успешно добавлены в очередь."}


@loans_router.post("/{book_id}/return", response=QueueResponse, auth=JWTAuth())
def return_book(request, book_id: int):
    """Вернуть книгу (ID пользователя проверяется через JWT токен)"""
    book = get_object_or_404(Book, id=book_id)
    user = request.auth

    loan = Loan.objects.filter(book=book, user=user, returned=False).first()
    if not loan:
        return {"status": "error", "message": "У вас нет активной аренды для этой книги."}

    loan.returned = True
    loan.save()

    next_reader = QueueEntry.objects.filter(book=book, status='waiting').first()

    if next_reader:
        next_reader.status = 'completed'
        next_reader.save()

        return_time = timezone.now() + timedelta(hours=1)
        Loan.objects.create(book=book, user=next_reader.user, return_by=return_time)

        return {
            "status": "transferred",
            "message": f"Книга возвращена и автоматически передана следующему читателю в очереди: {next_reader.user.username}."
        }

    book.available_copies += 1
    book.save()
    return {"status": "success", "message": "Книга успешно возвращена на полку. Очередь пуста."}
