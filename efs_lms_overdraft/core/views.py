from django.http import JsonResponse

def ping(request):
    return JsonResponse({"service": "efs_lms_overdraft", "status": "ok"})
