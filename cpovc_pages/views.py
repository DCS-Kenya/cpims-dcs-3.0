from django.shortcuts import render
from datetime import datetime, timedelta
from django.utils import timezone

from cpovc_auth.perms import dates


def pages_home(request):
    """Pages home."""
    try:
        context = {"dates": dates }
        today = datetime.now()
        kesho = today + timedelta(days=1)
        todate = str(today.strftime("%d-%b"))
        evedate = str(kesho.strftime("%d-%b"))
        # Get the Holiday
        fdate = str(today.strftime("%a %d, %B %Y"))
        fday = None
        h_prefix = 'Today is'
        holiday = dates[todate] if todate in dates else None
        if not holiday:
            h_prefix += ' eve of'
            holiday = dates[evedate] if evedate in dates else None
        if holiday:
        	fday = "%s %s" % (h_prefix, holiday)
        context["holiday"] = fday
        context["fdate"] = fdate
        context["fday"] = todate
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
