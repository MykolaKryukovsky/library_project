from django.db import models
from django.contrib.auth.models import User


class Book(models.Model):
    title = models.CharField(max_length=255, verbose_name="Название")
    author = models.CharField(max_length=255, verbose_name="Автор")
    genre = models.CharField(max_length=100, verbose_name="Жанр")
    available_copies = models.PositiveIntegerField(default=1, verbose_name="Доступные копии")

    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"

    def __str__(self):
        return f"{self.title} — {self.author}"


class Loan(models.Model):
    """Активная аренда книги читателем"""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="loans")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="loans")
    borrowed_at = models.DateTimeField(auto_now_add=True, verbose_name="Взята в")
    return_by = models.DateTimeField(verbose_name="Вернуть до")
    returned = models.BooleanField(default=False, verbose_name="Возвращена")

    class Meta:
        verbose_name = "Аренда"
        verbose_name_plural = "Аренды"


class QueueEntry(models.Model):
    """Очередь читателей на получение книги"""
    STATUS_CHOICES = [
        ('waiting', 'В ожидании'),
        ('completed', 'Книга получена'),
    ]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="queue")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="library_queue")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата входа в очередь")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')

    class Meta:
        ordering = ['created_at']
        verbose_name = "Запись в очереди"
        verbose_name_plural = "Очередь читателей"
        