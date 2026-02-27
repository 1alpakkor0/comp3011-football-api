from django.shortcuts import render

# Create your views here.

from django.http import JsonResponse

def health(request):
    return JsonResponse({"status": "ok", "service": "COMP3011 football API"})
