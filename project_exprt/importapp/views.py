import pandas as pd
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.contrib import messages
from django.db import transaction
from .models import DataImport
import chardet
import re
from typing import Optional
from io import BytesIO

def sanitize_name(name: str) -> str:
    """Утилита для очистки имен таблиц и столбцов"""
    name = re.sub(r'[^\w]', '_', str(name).lower())
    name = re.sub(r'_+', '_', name)
    return name.strip('_')[:63]

def detect_file_format(file) -> tuple:
    """Определяет формат файла и его кодировку"""
    filename = file.name.lower()
    
    # Для CSV и текстовых файлов определяем кодировку
    if filename.endswith('.csv') or '.' not in filename:
        sample = file.read(1024)
        file.seek(0)
        encoding = chardet.detect(sample)['encoding']
        return 'csv', encoding
    
    # Для известных форматов
    formats = {
        '.xlsx': ('excel', None),
        '.xls': ('excel', None),
        '.json': ('json', None),
        '.parquet': ('parquet', None),
        '.feather': ('feather', None)
    }
    
    for ext, (fmt, enc) in formats.items():
        if filename.endswith(ext):
            return fmt, enc
    
    return 'unknown', None

def read_file_to_dataframe(file, file_format: str, encoding: Optional[str] = None) -> pd.DataFrame:
    """Читает файл в DataFrame с обработкой ошибок"""
    try:
        if file_format == 'csv':
            # Пробуем разные разделители
            for sep in [',', ';', '\t', '|']:
                try:
                    file.seek(0)
                    return pd.read_csv(file, sep=sep, encoding=encoding, on_bad_lines='warn')
                except:
                    continue
            file.seek(0)
            return pd.read_csv(file, sep=None, engine='python', encoding=encoding)
        
        elif file_format == 'excel':
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
            file_format, encoding = detect_file_format(file)
            df = read_file_to_dataframe(file, file_format, encoding)
            
            # Очищаем имена столбцов
            df.columns = [sanitize_name(col) for col in df.columns]
            
            # Сохраняем DataFrame в сессии для предпросмотра
            request.session['import_data'] = {
                'df_json': df.head(100).to_json(orient='records'),
                'file_name': file.name,
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
        return HttpResponseForbidden("Метод не разрешен")
    
    try:
        import_data = request.session.get('import_data')
        if not import_data:
            raise ValueError("Данные для импорта не найдены")
        
        table_name = sanitize_name(request.POST.get('table_name', ''))
        if not table_name:
            raise ValueError("Не указано имя таблицы")
        
        # Восстанавливаем DataFrame из сессии
        df = pd.read_json(import_data['df_json'])
        
        # Создаем таблицу и импортируем данные
        model, import_record = DataImport.create_table_from_dataframe(
            table_name=table_name,
            df=df
        )
        
        # Сохраняем данные
        records = df.to_dict('records')
        model.objects.bulk_create([model(**r) for r in records])
        
        # Обновляем счетчик строк
        import_record.row_count = len(records)
        import_record.save()
        
        # Очищаем сессию
        del request.session['import_data']
        
        messages.success(request, f"Данные успешно импортированы в таблицу {table_name}")
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
        'preview_data': import_data['df_json'],
        'default_table_name': sanitize_name(import_data['file_name'].split('.')[0])
    }
    
    return render(request, 'preview.html', context)

def table_list(request):
    """Список всех импортированных таблиц"""
    tables = DataImport.objects.all().order_by('-created_at')
    return render(request, 'table_list.html', {'tables': tables})

def table_detail(request, table_name):
    """Просмотр содержимого таблицы"""
    try:
        # Получаем модель для динамической таблицы
        model = DataImport.get_dynamic_model(table_name)
        if not model:
            raise ValueError(f"Таблица {table_name} не найдена")
        
        # Получаем данные с пагинацией
        page = int(request.GET.get('page', 1))
        per_page = 50
        total = model.objects.count()
        data = model.objects.all()[(page-1)*per_page : page*per_page]
        
        context = {
            'table_name': table_name,
            'columns': [f.name for f in model._meta.get_fields() if f.name != 'id'],
            'data': data,
            'page': page,
            'total_pages': (total // per_page) + 1,
            'total_rows': total
        }
        
        return render(request, 'table_detail.html', context)
    
    except Exception as e:
        messages.error(request, str(e))
        return redirect('table_list')

@transaction.atomic
def table_delete(request, table_name):
    """Удаление таблицы с подтверждением"""
    if request.method == 'POST':
        try:
            DataImport.delete_table(table_name)
            messages.success(request, f"Таблица {table_name} успешно удалена")
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