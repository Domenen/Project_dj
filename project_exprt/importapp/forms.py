from django.forms import ModelForm
from django import forms
from .models import UploadedFile


class UploadFileForm(forms.Form):
    file = forms.FileField(label="Выберите файл")


class UploadFileModelForm(ModelForm):
    class Meta:
        model = UploadedFile
        fields = ['file']