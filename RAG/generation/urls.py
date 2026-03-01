from django.urls import path
from . import views

urlpatterns = [
    path("", views.generation_home, name="generation_home"),
    path("create-originator/", views.create_originator, name="create_originator"),


    path("generation/", views.generation_page, name="generation_page"),
    path("run-generation/", views.run_generation, name="run_generation"),

    path("convert_to_json/", views.convert_to_json, name="convert_to_json"),


## ------ delete embeddings and tokenised text ------

    path("flush-rag-data/", views.flush_rag_data, name="flush_rag_data"),  # NEW
    
    path(
        "generation/post-financial-data/",
        views.post_financial_data,
        name="post_financial_data",
    ),


    # NEW placeholder endpoints
    path(
        "ar-ledger/",
        views.AR_LedgerData,
        name="ar_ledger_data",
    ),
    path(
        "ap-ledger/",
        views.AP_LedgerDat,
        name="ap_ledger_dat",
    ),
    path(
        "fixed-assets-vehicles/",
        views.Fixed_assets_vehicles,
        name="fixed_assets_vehicles",
    ),
    path(
        "fixed-assets-plant-equipment/",
        views.Fixed_assets_plant_equipment,
        name="fixed_assets_plant_equipment",
    ),


    path("api/post-ledger-data/", views.post_ledger_data, name="post_ledger_data"),


]
