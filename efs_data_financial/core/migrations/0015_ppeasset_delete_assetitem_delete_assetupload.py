from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_assetitem_abn_assetitem_transaction_id"),  # your last applied core migration
    ]

    operations = [
        migrations.CreateModel(
            name="PPEAsset",
            fields=[
                ("row_id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("upload_group", models.UUIDField(default=uuid.uuid4, db_index=True)),
                ("file", models.FileField(upload_to="uploads/asset_lists/", blank=True, null=True)),
                ("original_filename", models.CharField(max_length=255, blank=True, null=True)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("abn", models.CharField(max_length=20, blank=True, null=True, db_index=True)),
                ("transaction_id", models.CharField(max_length=64, blank=True, null=True, db_index=True)),
                ("originator", models.CharField(max_length=200, blank=True, null=True)),
                ("asset_number", models.CharField(max_length=100, blank=True, null=True)),
                ("asset", models.CharField(max_length=255, blank=True, null=True)),
                ("make", models.CharField(max_length=255, blank=True, null=True)),
                ("type", models.CharField(max_length=255, blank=True, null=True)),
                ("serial_no", models.CharField(max_length=255, blank=True, null=True, db_index=True)),
                ("rego_no", models.CharField(max_length=255, blank=True, null=True, db_index=True)),
                ("year_of_manufacture", models.IntegerField(blank=True, null=True)),
                ("fair_market_value_ex_gst", models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)),
                ("orderly_liquidation_value_ex_gst", models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)),
            ],
            options={"db_table": "ppe_assets"},
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="AssetItem"),
                migrations.DeleteModel(name="AssetUpload"),
            ],
            database_operations=[
                migrations.RunSQL("DROP TABLE IF EXISTS core_assetitem CASCADE;", reverse_sql=migrations.RunSQL.noop),
                migrations.RunSQL("DROP TABLE IF EXISTS core_assetupload CASCADE;", reverse_sql=migrations.RunSQL.noop),
            ],
        ),

        migrations.AddIndex(model_name="ppeasset", index=models.Index(fields=["abn"], name="core_ppe_abn_idx")),
        migrations.AddIndex(model_name="ppeasset", index=models.Index(fields=["transaction_id"], name="core_ppe_tx_idx")),
        migrations.AddIndex(model_name="ppeasset", index=models.Index(fields=["upload_group"], name="core_ppe_upgrp_idx")),
        migrations.AddIndex(model_name="ppeasset", index=models.Index(fields=["asset_number"], name="core_ppe_assetnum_idx")),
        migrations.AddIndex(model_name="ppeasset", index=models.Index(fields=["make"], name="core_ppe_make_idx")),
        migrations.AddIndex(model_name="ppeasset", index=models.Index(fields=["serial_no"], name="core_ppe_serial_idx")),
        migrations.AddIndex(model_name="ppeasset", index=models.Index(fields=["rego_no"], name="core_ppe_rego_idx")),
    ]
