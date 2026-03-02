from django.db import models
from django.utils import timezone
import uuid

class RetrievalLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query_text = models.TextField()
    results = models.JSONField()  # stores chunks as JSON
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Query: {self.query_text[:50]}... @ {self.created_at}"
