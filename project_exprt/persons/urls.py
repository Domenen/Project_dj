from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views


urlpatterns = [
    path('', views.page_auth, name='auth'),
    path('home/', views.home_page, name='home'),
    path('persons/', views.index_page, name='persons'),
    path('documents/', views.documents_page, name='documents'),
    path('downloads/', views.downloads_page, name='downloads'),
    path('downloads_2/', views.downloads_page_2, name='downloads_2'),
    path('projects/', views.procjets_page, name='projects'),
    path('user_cab/', views.user_cab, name='user_cab')    
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)