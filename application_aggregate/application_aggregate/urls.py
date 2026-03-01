# application_aggregate/application_aggregate/urls.py
from django.contrib import admin
from django.urls import path, include
from aggregate import views as agg_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # explicit application routes (as you already have)
    path('api/applications/',                agg_views.list_applications,        name='agg_list_applications'),
    path('api/applications/ingest/',         agg_views.ingest_application,       name='agg_ingest_application'),
    path('api/applications/state/',          agg_views.update_state_fallback,    name='agg_update_state_fallback'),
    path('api/applications/<str:tx>/',       agg_views.get_application,          name='agg_get_application'),
    path('api/applications/<str:tx>/state/', agg_views.update_state,             name='agg_update_state'),

    # 🔁 Compatibility alias so old clients posting to /api/receive-application-data/ keep working
    path('api/receive-application-data/',    agg_views.receive_application_data, name='agg_receive_application_data_api'),

    # include everything else (this exposes /receive-application-data/ too)
    path('', include('aggregate.urls')),
]
