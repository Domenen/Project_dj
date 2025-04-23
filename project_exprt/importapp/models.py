from django.db import models
from django.db import connection
from django.db.utils import IntegrityError
import pandas as pd
import re


class DataImport(models.Model):
    """
    Модель для хранения информации о созданных таблицах
    """
    table_name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    columns_info = models.JSONField()
    row_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Импорт данных"
        verbose_name_plural = "Импорты данных"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.table_name} ({self.created_at.strftime('%Y-%m-%d')})"

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Очистка имени таблицы и колонок"""
        name = re.sub(r'[^\w]', '_', str(name).lower())
        name = re.sub(r'_+', '_', name)
        return name.strip('_')[:63]

    @staticmethod
    def dtype_to_field(dtype: str, column_name: str) -> str:
        """Преобразование типа данных Pandas в SQL-типы PostgreSQL"""
        dtype = str(dtype).lower()
        if dtype in ['int64', 'int32', 'int']:
            return 'INTEGER'
        elif dtype in ['float64', 'float32', 'float']:
            return 'FLOAT'
        elif dtype == 'bool':
            return 'BOOLEAN'
        elif dtype.startswith('datetime'):
            return 'TIMESTAMP'
        else:
            return 'TEXT'

    @classmethod
    def create_table_from_dataframe(cls, table_name: str, df: pd.DataFrame) -> None:
        """Создает новую таблицу в базе данных на основе предоставленного DataFrame."""

        # Стандартизация имени таблицы
        table_name = cls.sanitize_name(table_name)
        if not table_name:
            raise ValueError("Некорректное имя таблицы")

        # Проверяем наличие существующего экземпляра таблицы
        if cls.objects.filter(table_name=table_name).exists():
            raise IntegrityError(f"Таблица '{table_name}' уже существует")

        # Формируем SQL для создания таблицы
        columns_sql = []
        for col in df.columns:
            if not col:
                continue
            dtype = cls.dtype_to_field(str(df[col].dtype), col)
            columns_sql.append(f'"{col}" {dtype}')

        if not columns_sql:
            raise ValueError("Нет допустимых колонок для создания таблицы")

        if 'id' not in df.columns:
            columns_sql.insert(0, '"id" SERIAL PRIMARY KEY')

        # Создаем таблицу
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table_name}" (\n{",\n".join(columns_sql)}\n);'
            )
            
            #  Удалить когда перенесется все на PostgeSql 
            if connection.vendor == 'sqlite':
                cursor.execute('COMMIT;')

        cls.objects.create(
            table_name=table_name,
            columns_info=dict(zip(df.columns, [str(df[col].dtype) for col in df.columns])),
            row_count=len(df)
        )

    @classmethod
    def delete_table(cls, table_name: str) -> bool:
        """Удаляет таблицу."""
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}";')
            else:
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;')
        
        try:
            cls.objects.get(table_name=table_name).delete()
            return True
        except cls.DoesNotExist:
            return False
        
    @classmethod
    def get_table_columns(cls, table_name: str) -> list:
        """Получает список колонок таблицы"""
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 0;')
            return [col[0] for col in cursor.description]