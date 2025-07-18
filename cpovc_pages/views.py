from django.shortcuts import render


def pages_home(request):
    """Pages home."""
    try:
        context = {}
        return render(request, 'pages/home.html', context)
    except Exception as e:
        raise e

def pages_apps(request):
    """Pages home."""
    try:
        context = {}
        return render(request, 'pages/apps.html', context)
    except Exception as e:
        raise e



def pages_partners(request):
    """Pages home."""
    try:
        context = {}
        return render(request, 'pages/partners.html', context)
    except Exception as e:
        raise e
