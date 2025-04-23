import pandas as pd
from django.urls import reverse
from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.contrib import messages
from django.db import transaction, connection
from .models import DataImport
import logging
import io
import re
from io import BytesIO


logger = logging.getLogger(__name__)


def sanitize_name(name: str) -> str:
    """Утилита для очистки имен таблиц и столбцов"""
    name = re.sub(r'[^\w]', '_', str(name).lower())
    name = re.sub(r'_+', '_', name)
    return name.strip('_')[:63]

def home_page(request):
    return render(request, 'home_page.html')


def detect_file_format(file) -> tuple:
    """Определяет формат файла"""
    file_name, file_format = file.name.lower().split(".")

    # Для известных форматов
    formats = ["csv", "xlsx", "xls", "json", "parquet", "feather"]

    # Известен нам формат или нет
    if file_format not in formats:
        return HttpResponseBadRequest("Неизвестный формат файла")

    return file_name, file_format


def read_file_to_dataframe(file, file_format) -> pd.DataFrame:
    """Читает файл в DataFrame с обработкой ошибок"""
    try:
        if file_format == 'csv':
            return pd.read_csv(file, encoding="utf-8")
        
        elif file_format == 'xlsx' or file_format == 'xls':
            return pd.read_excel(file)
        
        elif file_format == 'json':
            return pd.read_json(file)
        
        elif file_format == 'parquet':
            return pd.read_parquet(BytesIO(file.read()))
        
        elif file_format == 'feather':
            return pd.read_feather(BytesIO(file.read()))
        
        else:
            raise ValueError("Неподдерживаемый формат файла")
    
    except Exception as e:
        raise ValueError(f"Ошибка чтения файла: {str(e)}")


def upload_file(request):
    """Обработчик загрузки файла"""
    if request.method == 'POST':
        if 'file' not in request.FILES:
            return HttpResponseBadRequest("Файл не был отправлен")
        
        file = request.FILES['file']
        if file.size > 10 * 1024 * 1024:  # 10MB лимит
            return HttpResponseBadRequest("Файл слишком большой (максимум 10MB)")
        
        try:
            # Определяем формат и читаем файл
            file_name, file_format = detect_file_format(file)
            df = read_file_to_dataframe(file, file_format)
            
            request.session['full_data'] = df.to_json(orient='records', force_ascii=False)

            # Сохраняем DataFrame в сессии для предпросмотра
            preview_data = df.head().to_dict('records')
            request.session['import_data'] = {
                'preview_data': preview_data,
                'file_name': file_name,
                'row_count': len(df),
                'columns': list(df.columns)
            }
            
            return redirect('preview_data')
        
        except Exception as e:
            messages.error(request, f"Ошибка обработки файла: {str(e)}")
            return render(request, 'upload.html')
    
    return render(request, 'upload.html')

@transaction.atomic
def save_to_database(request):
    """Сохранение данных в БД"""
    if request.method != 'POST':
        return HttpResponseForbidden("Запрещённый метод")

    try:
        # Извлекаем данные из сессии
        full_data_json = request.session.get('full_data')
        if not full_data_json:
            raise ValueError("Отсутствуют данные для импорта")

        df = pd.read_json(io.StringIO(full_data_json))

        table_name = sanitize_name(request.POST.get('table_name', ''))
        if not table_name:
            raise ValueError("Имя таблицы не задано")

        DataImport.create_table_from_dataframe(table_name, df)

        # Подготавливаем данные для вставки
        columns = [f'"{col}"' for col in df.columns]
        placeholders = ', '.join(['%s'] * len(df.columns))
        
        # SQL для вставки данных
        insert_sql = f'INSERT INTO "{table_name}" ({", ".join(columns)}) VALUES ({placeholders})'
        
        # Конвертируем данные в список кортежей
        data_tuples = [tuple(row) for row in df.to_numpy()]
        with connection.cursor() as cursor:
            cursor.executemany(insert_sql, data_tuples)

        # Обновляем счётчик количества строк
        import_record = DataImport.objects.get(table_name=table_name)
        import_record.row_count = len(df)
        import_record.save()

        # Очищаем сессионные данные
        del request.session['import_data']
        del request.session['full_data']

        messages.success(request, f"Данные успешно сохранены в таблицу {table_name}. Всего записей: {len(df)}.")
        return redirect('import_success', table_name=table_name)

    except Exception as e:
        messages.error(request, f"Ошибка импорта: {str(e)}")
        return redirect('preview_data')

def preview_data(request):
    """Страница предпросмотра данных перед импортом"""
    import_data = request.session.get('import_data')
    if not import_data:
        return redirect('upload_file')
    
    context = {
        'file_name': import_data['file_name'],
        'row_count': import_data['row_count'],
        'columns': import_data['columns'],
        'preview_data': import_data['preview_data'],
        'default_table_name': sanitize_name(import_data['file_name'].split('.')[0])
    }
    
    return render(request, 'preview.html', context)

def table_list(request):
    """Отображение списка импортированных таблиц"""
    tables = DataImport.objects.all().order_by('-created_at')
    return render(request, 'table_list.html', {'tables': tables})

def table_detail(request, table_name):
    """Просмотр содержимого таблицы"""
    try:
        try:
            import_record = DataImport.objects.get(table_name=table_name)
        except DataImport.DoesNotExist:
            raise ValueError(f"Таблица {table_name} не найдена в метаданных")

        # Получаем данные с пагинацией
        page = int(request.GET.get('page', 1))
        per_page = 50
        offset = (page - 1) * per_page

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}";')
            total = cursor.fetchone()[0]

            cursor.execute(
                f'SELECT * FROM "{table_name}" LIMIT %s OFFSET %s;',
                [per_page, offset]
            )
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        context = {
            'table_name': table_name,
            'columns': columns,
            'data': rows,
            'page': page,
            'total_pages': (total // per_page) + 1,
            'total_rows': total
        }

        return render(request, 'table_detail.html', context)

    except Exception as e:
        messages.error(request, f"Ошибка: {str(e)}")
        logger.exception(f"Ошибка при просмотре таблицы {table_name}")
        return redirect('table_list')

@transaction.atomic
def table_delete(request, table_name):
    """Удаление таблицы с подтверждением"""
    if request.method == 'POST':
        try:
            deleted = DataImport.delete_table(table_name)
            if deleted:
                messages.success(request, f"Таблица {table_name} успешно удалена")
            else:
                messages.warning(request, f"Таблицу {table_name} невозможно удалить")
            return redirect('table_list')
        except Exception as e:
            messages.error(request, f"Ошибка удаления: {str(e)}")
            return redirect('table_detail', table_name=table_name)

    return render(request, 'confirm_delete.html', {'table_name': table_name})

def import_success(request, table_name):
    """Страница успешного импорта"""
    return render(request, 'import_success.html', {
        'table_name': table_name,
        'table_url': reverse('table_detail', args=[table_name])
    })