from django.contrib import admin

from .models import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('pk', 'name', 'adress', 'constract', 'start_project', 'finish_project')
    list_display_links = ('pk', 'name', 'adress', 'constract', 'start_project', 'finish_project')