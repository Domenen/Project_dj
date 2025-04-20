from django.db import models
from django.db import connection
from django.db.utils import ProgrammingError, IntegrityError
import pandas as pd
import re
from typing import Type, Optional, Tuple

class DataImport(models.Model):
    """
    Мета-модель для хранения информации о созданных таблицах
    """
    table_name = models.CharField(max_length=255, unique=True, verbose_name="Имя таблицы")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    columns_info = models.JSONField(verbose_name="Информация о столбцах")
    row_count = models.PositiveIntegerField(default=0, verbose_name="Количество строк")

    class Meta:
        verbose_name = "Импорт данных"
        verbose_name_plural = "Импорты данных"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.table_name} ({self.created_at.strftime('%Y-%m-%d')})"

    @classmethod
    def sanitize_name(cls, name: str) -> str:
        """
        Приводит имя к допустимому формату для SQL:
        - Заменяет спецсимволы на _
        - Удаляет повторяющиеся _
        - Переводит в нижний регистр
        """
        name = re.sub(r'[^\w]', '_', str(name).lower())
        name = re.sub(r'_+', '_', name)
        return name.strip('_')[:63]  # Ограничение длины имени в PostgreSQL

    @classmethod
    def dtype_to_field(cls, dtype: str) -> Type[models.Field]:
        """
        Сопоставляет типы Pandas с полями Django
        """
        dtype = str(dtype).lower()
        
        if dtype in ['int64', 'int32', 'int']:
            return models.IntegerField
        elif dtype in ['float64', 'float32', 'float']:
            return models.FloatField
        elif dtype == 'bool':
            return models.BooleanField
        elif dtype.startswith('datetime'):
            return models.DateTimeField
        else:  # object, string и все остальное
            return models.TextField

    @classmethod
    def create_table_from_dataframe(
        cls,
        table_name: str,
        df: pd.DataFrame,
        index: bool = False
    ) -> Tuple[Type[models.Model], 'DataImport']:
        """
        Создает динамическую модель и таблицу в БД на основе DataFrame
        
        Args:
            table_name: Желаемое имя таблицы
            df: DataFrame с данными
            index: Включать ли индекс в таблицу
            
        Returns:
            Tuple: (Динамическая модель, Объект DataImport)
        """
        # Подготавливаем имя таблицы
        table_name = cls.sanitize_name(table_name)
        if not table_name:
            raise ValueError("Недопустимое имя таблицы")

        # Проверяем, что таблицы с таким именем нет
        if cls.objects.filter(table_name=table_name).exists():
            raise IntegrityError(f"Таблица '{table_name}' уже существует")

        # Собираем информацию о столбцах
        columns_info = {}
        attrs = {
            '__module__': cls.__module__,
            'Meta': type('Meta', (), {
                'app_label': cls._meta.app_label,
                'db_table': table_name,
                'verbose_name': table_name,
                'managed': False,
            }),
        }

        # Добавляем поля для каждого столбца
        for col in df.columns:
            col_name = cls.sanitize_name(col)
            if not col_name:
                continue

            field_type = cls.dtype_to_field(df[col].dtype)
            attrs[col_name] = field_type(
                null=True,
                blank=True,
                verbose_name=col
            )
            columns_info[col_name] = str(df[col].dtype)

        # Добавляем индекс если требуется
        if index and df.index.name:
            index_name = cls.sanitize_name(df.index.name) or 'index'
            attrs[index_name] = models.IntegerField(primary_key=True)

        # Создаем динамическую модель
        model = type(table_name, (models.Model,), attrs)

        # Создаем таблицу в БД
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(model)

        # Сохраняем метаинформацию
        import_record = cls.objects.create(
            table_name=table_name,
            columns_info=columns_info,
            row_count=len(df)
        )

        return model, import_record

    @classmethod
    def get_dynamic_model(cls, table_name: str) -> Optional[Type[models.Model]]:
        """
        Возвращает динамическую модель для таблицы или None если не найдена
        """
        try:
            import_record = cls.objects.get(table_name=table_name)
            
            attrs = {
                '__module__': cls.__module__,
                'Meta': type('Meta', (), {
                    'app_label': cls._meta.app_label,
                    'db_table': table_name,
                    'managed': False,
                }),
            }

            # Создаем поля на основе сохраненной информации
            for col_name, dtype in import_record.columns_info.items():
                field_type = cls.dtype_to_field(dtype)
                attrs[col_name] = field_type(
                    null=True,
                    blank=True,
                    verbose_name=col_name
                )

            return type(table_name, (models.Model,), attrs)
        except cls.DoesNotExist:
            return None

    @classmethod
    def delete_table(cls, table_name: str) -> None:
        """
        Удаляет таблицу и запись о ней
        """
        model = cls.get_dynamic_model(table_name)
        if model:
            with connection.schema_editor() as schema_editor:
                schema_editor.delete_model(model)
            cls.objects.filter(table_name=table_name).delete()