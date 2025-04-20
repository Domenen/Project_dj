from django.urls import path
from . import views

# app_name = 'data_importer'  # Пространство имен для URL

urlpatterns = [
    # Главная страница - загрузка файла
    path('', views.upload_file, name='upload_file'),
    
    # Просмотр списка всех импортированных таблиц
    path('tables/', views.table_list, name='table_list'),
    
    # Просмотр содержимого конкретной таблицы
    path('tables/<str:table_name>/', views.table_detail, name='table_detail'),
    
    # Удаление таблицы (с подтверждением)
    path('tables/<str:table_name>/delete/', views.table_delete, name='table_delete'),
    
    # Страница успешного импорта
    path('import-success/', views.import_success, name='import_success'),
    
    # Страница предпросмотра данных перед импортом
    path('preview/', views.preview_data, name='preview_data'),
]

# Дополнительные настройки:
"""
1. Все URL имеют понятные имена (name) для удобного обращения в шаблонах
2. Используется пространство имен (app_name) для избежания конфликтов
3. Имена таблиц (table_name) передаются как строковые параметры
4. Порядок URL организован от более общих к более конкретным
5. Добавлен URL для удаления таблиц с подтверждением
"""

# urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)