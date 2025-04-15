from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views


urlpatterns = [
    path('', views.page_auth, name='auth'),
    path('persons/', views.index_page, name='persons'),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)