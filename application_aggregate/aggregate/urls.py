from django.urls import path
from . import views


app_name = "aggregate"

urlpatterns = [
    path("receive-application-data/", views.receive_application_data, name="receive_application_data"),
    path("receive-tf-application-data/", views.receive_tf_application_data, name="receive_tf_application_data"),
    path("api/receive-scf-application-data/", views.receive_scf_application_data),

    path("api/applications/", views.list_applications, name="agg_list_applications"),
    path("api/applications/<str:tx>/", views.get_application, name="agg_get_application"),
    path("api/applications/<str:tx>/state/", views.update_state, name="agg_update_state"),
    path("api/applications/state/", views.update_state_fallback, name="agg_update_state_fallback"),
    path("api/applications/ingest/", views.ingest_application, name="agg_ingest_application"),




# display applications in kanban board
    path("api/applications/", views.applications_list, name="applications_list"),



    # Terms (make paths unique!)
    path("application/modal/terms/", views.terms_modal, name="terms_modal"),
    path("application/terms/fetch/", views.terms_fetch, name="terms_fetch"),        # ← Agents uses this
    path("application/terms/get/",   views.fetch_terms, name="terms_get_single"),   # ← Modal “one row” shape
    path("application/terms/save/",  views.save_terms,  name="terms_save"),
    path("sales/application/terms/fetch/", views.terms_fetch, name="sales_terms_fetch"),
    path("sales/application/terms/save/",  views.save_terms,  name="sales_terms_save"),




   # manually create a deal
    path("api/applications/ingest/", views.ingest_application, name="ingest_application"),
 
 

 # create a link between deals 

    path("application/abns/", views.application_abns, name="application_abns"),
    path("application/links/save/", views.application_links_save, name="application_links_save"),

 # search for link between deals 

    # 1. For the ABN dropdown in the "Link Entities" modal
    #    GET http://localhost:8016/aggregate/abns/


    # 3. To FETCH the network graph for a given ABN
    #    GET http://localhost:8016/aggregate/linked-entities/?abn=11111111111
    path("linked-entities/", views.linked_entities, name="application_linked_entities"),

        # ---- SALES-COMPAT SHIMS (to match the JS that calls /sales/...) ----

    path("sales/abns/", views.application_abns, name="sales_abns"),
    path("sales/acns/", views.application_acns, name="sales_acns"),
    path("sales/link-entities/", views.application_links_save, name="sales_link_entities"),
    path("sales/linked-entities/", views.linked_entities, name="sales_linked_entities"),

    path("api/applications/<str:tx>/delete/", views.delete_application, name="delete_application"),

    # NEW: Deals (Sales Review) for RAG Generation service
    path(
        "api/sales-review-deals/",
        views.sales_review_deals,
        name="sales_review_deals",
    ),


   path("api/aggregate/by-tx/<str:tx>/", views.aggregate_by_tx, name="aggregate_by_tx"),


# right side panel data fetching 
 path("api/live-deals/", views.live_deals, name="live_deals"),

#save deal conditions 
path("api/deal-conditions/", views.DealConditionCreateView.as_view(), name="deal_conditions_create"),

#Fetch deal conditions for efs_agents service 
path("api/deal-conditions/by-tx/<str:tx>/", views.deal_conditions_by_tx, name="deal_conditions_by_tx"),


]




