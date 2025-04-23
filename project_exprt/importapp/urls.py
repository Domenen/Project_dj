from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # Основные маршруты
    path('', views.upload_file, name='upload_file'),
    path('preview/', views.preview_data, name='preview_data'),
    path('save/', views.save_to_database, name='save_to_database'),
    
    # Работа с таблицами
    path('tables/', views.table_list, name='table_list'),
    path('tables/<str:table_name>/', views.table_detail, name='table_detail'),
    path('tables/<str:table_name>/delete/', views.table_delete, name='table_delete'),
    
    # Статусные страницы
    path('import-success/<str:table_name>/', views.import_success, name='import_success'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)