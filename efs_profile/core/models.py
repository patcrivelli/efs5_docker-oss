from django.db import models

class Originator(models.Model):
    originator = models.CharField(max_length=255, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.CharField(max_length=255, null=True, blank=True)  # Changed to CharField
    id = models.AutoField(primary_key=True)

    def __str__(self):
        return self.originator
