from django.db import models


class Person(models.Model):
    name = models.CharField(
        'ФИО',
        max_length=200,
        unique=True
    )

    job_title = models.CharField(
        'Должность',
        max_length=200,
        unique=True
    )
    birthday = models.DateField(
        'Дата рождения',
    )

    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'

    def __str__(self):
        return self.name