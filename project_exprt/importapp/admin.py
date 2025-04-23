from django.contrib import admin

from .models import DataImport

@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = ('table_name', 'created_at', 'row_count')
    list_filter = ('created_at',)
    search_fields = ('table_name',)
    readonly_fields = ('created_at', 'columns_info', 'row_count')
    fieldsets = (
        (None, {
            'fields': ('table_name', 'created_at')
        }),
        ('Дополнительная информация', {
            'fields': ('row_count', 'columns_info'),
            'classes': ('collapse',)
        }),
    )