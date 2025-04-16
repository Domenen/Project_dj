from django.contrib import admin

from .models import Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('pk', 'name', 'job_title', 'birthday')
    list_display_links = ('pk', 'name', 'job_title', 'birthday')
