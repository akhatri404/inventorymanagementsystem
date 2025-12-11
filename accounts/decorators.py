from django.shortcuts import redirect
from django.contrib import messages

def role_required(actions):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.role == 'Admin':
                return view_func(request, *args, **kwargs)
            elif request.user.role == 'Staff' and any(a in ['view','add','update'] for a in actions):
                return view_func(request, *args, **kwargs)
            elif request.user.role == 'User' and actions == ['view']:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "You do not have permission for this action.")
                return redirect('dashboard-home')
        return wrapper
    return decorator
