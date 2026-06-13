import jwt
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.conf import settings


User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_string):
    """
    Асинхронно отримує користувача з бази даних за допомогою JWT-токена.
    Декодує переданий рядок токена за допомогою секретного ключа Django.
    Якщо токен валідний, повертає відповідний об'єкт користувача. У разі
    будь-якої помилки валідації або якщо користувача не знайдено,
    повертає об'єкт `AnonymousUser`.
    Args:
        token_string (str): Рядок JWT-токена для автентифікації.
    Returns:
        User | AnonymousUser: Об'єкт автентифікованого користувача
            або `AnonymousUser`, якщо токен недійсний чи відсутній.
    """
    if not token_string:
        return AnonymousUser()
    try:
        payload = jwt.decode(token_string, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        return User.objects.get(id=user_id)
    except (jwt.ExpiredSignatureError, jwt.DecodeError, jwt.InvalidTokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Проміжне програмне забезпечення (Middleware) для автентифікації через JWT у Django Channels.
    Шукає JWT-токен спочатку в HTTP-заголовках (Headers) за стандартом `Bearer <token>`,
    а якщо він відсутній — перевіряє параметри URL-запиту (Query String).
    Валідує токен та додає об'єкт користувача в `scope["user"]`.
    """

    def __init__(self, inner):
        """
        Ініціалізує мідлвар.
        Args:
            inner (callable): Наступний ASGI-додаток або мідлвар у ланцюжку.
        """
        self.inner = inner

    async def __call__(self, scope, receive, send):
        """
        Обробляє вхідний запит з'єднання.
        Шукає токен у заголовках або query-параметрах, автентифікує користувача
        та передає керування далі по ланцюжку.
        Args:
            scope (dict): Контекст поточного з'єднання (ASGI scope).
            receive (callable): Асинхронна функція для отримання подій.
            send (callable): Асинхронна функція для відправки подій.
        Returns:
            Asynchronous task: Результат виконання наступного додатка.
        """
        token = None

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            query_string = scope.get("query_string", b"").decode("utf-8")
            query_params = parse_qs(query_string)
            token_list = query_params.get("token", [None])
            token = token_list[0] if token_list else None

        scope["user"] = await get_user_from_token(token)

        return await self.inner(scope, receive, send)
