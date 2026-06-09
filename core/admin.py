from django.contrib import admin
from .models import Book, Loan, QueueEntry

admin.site.register(Book)
admin.site.register(Loan)
admin.site.register(QueueEntry)
