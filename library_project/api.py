from ninja import NinjaAPI
from core.router import books_router, loans_router, auth_router


api = NinjaAPI(
    title="Библиотека Книг API",
    version="1.0.0",
    description="Главная точка входа. Роутеры подключены из приложений проекта."
)

api.add_router("/auth", auth_router)
api.add_router("/books", books_router)
api.add_router("/loans", loans_router)
