from django.shortcuts import render

def home_page(request):
    return render(request, 'home.html')

def index_page(request):
    return render(request, 'persons.html')

def downloads_page(request):
    return render(request, 'downloads_files.html')

def downloads_page_2(request):
    return render(request, 'downloads_files_2.html')

def procjets_page(request):
    return render(request, 'projects.html')

def documents_page(request):
    return render(request, 'documents.html')

def page_auth(request):
    return render(request, 'auth.html')

def user_cab(request):
    return render(request, 'user_cab.html')

