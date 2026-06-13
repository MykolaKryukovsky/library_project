import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache


class GlobalConsumer(AsyncWebsocketConsumer):
    """
    Асинхронний WebSocket-консюмер для глобальних сповіщень та загального чату.
    Керує підключеннями користувачів, веде облік кількості онлайн-користувачів
    через Django Cache, а також розсилає пуш-сповіщення та повідомлення чату
    всім учасникам глобальної групи.
    """

    async def connect(self):
        """
        Обробляє підключення нового клієнта через WebSocket.
        Додає клієнта до глобальної групи, приймає з'єднання, збільшує
        лічильник користувачів в онлайні у кеші та розсилає оновлену
        кількість усім підключеним клієнтам.
        """
        self.group_name = "global_notifications"
        self.user = self.scope["user"]

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

        online_count = cache.get("online_users_count", 0) + 1
        cache.set("online_users_count", online_count)

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "send_online_count",
                "count": online_count
            }
        )

    async def disconnect(self, close_code):
        """
        Обробляє відключення клієнта від WebSocket.
        Зменшує лічильник онлайн-користувачів у кеші (контролюючи, щоб він не
        став меншим за нуль), розсилає оновлену кількість іншим учасникам
        та видаляє канал із глобальної групи.
        Args:
            close_code (int): Код закриття WebSocket-з'єднання.
        """
        online_count = cache.get("online_users_count", 1) - 1
        if online_count < 0:
            online_count = 0
        cache.set("online_users_count", online_count)

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "send_online_count",
                "count": online_count
            }
        )

        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Обробляє вхідні повідомлення від клієнта через WebSocket.
        Парсить JSON-дані та викликає відповідну дію залежно від поля `action`:
        - "send_push": надсилає пуш-сповіщення всім користувачам.
        - "send_chat_message": розсилає повідомлення в чат (тільки для авторизованих).
        Args:
            text_data (str): Текстові дані (JSON-рядок), отримані від клієнта.
        """
        data = json.loads(text_data)
        action = data.get("action")

        if action == "send_push":
            message_text = data.get("message", "Новое уведомление!")

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "send_notification",
                    "message": message_text
                }
            )

        elif action == "send_chat_message":
            if not self.user.is_authenticated:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": "Гости не могут писать сообщения. Пожалуйста, войдите в аккаунт!"
                }))
                return

            message_text = data.get("message", "")

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat_message",
                    "username": self.user.username,
                    "message": message_text
                }
            )

    async def send_online_count(self, event):
        """
        Обробник події "send_online_count" від channel layer.
        Відправляє поточну кількість онлайн-користувачів безпосередньо клієнту.
        Args:
            event (dict): Словник із даними події, містить ключ "count".
        """
        await self.send(text_data=json.dumps({
            "type": "online_count",
            "count": event["count"]
        }))

    async def send_notification(self, event):
        """
        Обробник події "send_notification" від channel layer.
        Відправляє пуш-сповіщення безпосередньо клієнту.
        Args:
            event (dict): Словник із даними події, містить ключ "message".
        """
        await self.send(text_data=json.dumps({
            "type": "push_notification",
            "message": event["message"]
        }))

    async def chat_message(self, event):
        """
        Обробник події "chat_message" від channel layer.
        Відправляє повідомлення чату з іменем автора безпосередньо клієнту.
        Args:
            event (dict): Словник із даними події, містить "username" та "message".
        """
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "username": event["username"],
            "message": event["message"]
        }))
