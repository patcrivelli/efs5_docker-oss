# /embeddings/models.py
import uuid
from django.db import models
from pgvector.django import VectorField  # ✅ pgvector integration

class Embedding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    element = models.OneToOneField(
        "chunking.Element",
        on_delete=models.CASCADE,
        related_name="embedding"
    )
    # pgvector field (set dimensions to match your embedding model)
    vector = VectorField(dimensions=768)   # e.g. MiniLM (384) or MPNet (768)
    model_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["model_name"]),   # optional index for queries
        ]
