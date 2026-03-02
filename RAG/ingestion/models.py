# apps/ingestion/models.py
import uuid
from django.db import models

class Document(models.Model):
    """
    A logical document (e.g., 'Apple Annual Report 2023') that can have multiple files/versions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Business metadata (optional but handy for reports)
    company_name = models.CharField(max_length=255)
    ticker_symbol = models.CharField(max_length=50, null=True, blank=True)
    fiscal_year = models.IntegerField(null=True, blank=True)

    # Provenance
    source = models.CharField(
        max_length=50,
        choices=[("upload","upload"), ("web","web"), ("api","api")],
        default="upload"
    )
    source_url = models.URLField(null=True, blank=True)

    # Taggable freeform metadata
    extra = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["company_name", "fiscal_year"])]

    def __str__(self):
        return f"{self.company_name} {self.fiscal_year or ''}".strip()


class DocumentFile(models.Model):
    """
    A concrete file (PDF/DOCX/XLSX/CSV, etc.) for a Document.
    Stored via Django Storage (filesystem/S3), not in DB blobs.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="files")

    file = models.FileField(upload_to="documents/%Y/%m/%d/")  # use S3 in prod
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)    # e.g. application/pdf
    byte_size = models.BigIntegerField()
    sha256 = models.CharField(max_length=64)        # de-dupe + lineage
    version = models.PositiveIntegerField(default=1)

    # Helpful for parsing/QA
    page_count = models.PositiveIntegerField(null=True, blank=True)   # PDFs
    sheet_names = models.JSONField(null=True, blank=True)             # Excel
    row_count = models.PositiveIntegerField(null=True, blank=True)    # CSVs

    uploaded_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("document", "version")]
        indexes = [models.Index(fields=["sha256"])]

    def __str__(self):
        return f"{self.original_filename} (v{self.version})"
