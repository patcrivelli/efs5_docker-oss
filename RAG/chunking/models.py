# chunking/models.py
import uuid
from django.db import models

class ExtractionRun(models.Model):
    """
    Records parser config used to create elements (reproducibility).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_file = models.ForeignKey("ingestion.DocumentFile", on_delete=models.CASCADE, related_name="extractions")
    parser = models.CharField(max_length=100)  # e.g. "pdfplumber", "docx2txt", "excel"
    parser_version = models.CharField(max_length=50, default="v1")
    params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Element(models.Model):
    """
    A normalized content unit extracted from a file: text block, table, chart image, etc.
    """
    TYPE_CHOICES = [
        ("text", "text"),
        ("table", "table"),
        ("chart", "chart"),
        ("figure", "figure"),
        ("metadata", "metadata"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    extraction = models.ForeignKey(ExtractionRun, on_delete=models.CASCADE, related_name="elements")
    document = models.ForeignKey("ingestion.Document", on_delete=models.CASCADE, related_name="elements")

    element_type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    # Locality within source
    page_number = models.IntegerField(null=True, blank=True)
    start_offset = models.IntegerField(null=True, blank=True)  # char offset for text
    end_offset = models.IntegerField(null=True, blank=True)

    # Payloads (use only what applies per type)
    text = models.TextField(null=True, blank=True)                   # for element_type="text"
    table_json = models.JSONField(null=True, blank=True)             # for tables
    image_path = models.CharField(max_length=500, null=True, blank=True)  # store via storage backend
    description = models.TextField(null=True, blank=True)            # OCR/alt text

    meta = models.JSONField(default=dict, blank=True)  # headers, bbox, font, confidence, etc.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["document", "element_type"]),
            models.Index(fields=["page_number"]),
        ]
