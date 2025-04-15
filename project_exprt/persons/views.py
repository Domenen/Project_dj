from django.shortcuts import render

def index_page(request):
    return render(request, 'persons.html')

def page_auth(request):
    return render(request, 'auth.html')