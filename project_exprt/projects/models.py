from django.db import models


class Project(models.Model):
    name = models.CharField(
        'Название проекта',
        max_length=200,
        unique=True
    )

    adress = models.CharField(
        'Адрес проекта',
        max_length=200,
        unique=True
    )

    constract = models.CharField(
        'Застройщик',
        max_length=200,
        unique=True
    )


    start_project = models.DateField(
        'Дата начала',
    )

    finish_project = models.DateField(
        'Дата завершения'
    )

    class Meta:
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'

    def __str__(self):
        return self.name