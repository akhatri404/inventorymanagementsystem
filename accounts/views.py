from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CustomUserCreationForm
from django.contrib.auth import login, authenticate, logout

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Admin verification
            user.save()
            messages.success(request, 'Signup successful! Wait for admin approval.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(username=email, password=password)

        if user:
            if not user.is_approved:
                messages.error(request, "Your account is awaiting admin approval.")
                return redirect('login')

            login(request, user)
            return redirect('dashboard-home')
        else:
            messages.error(request, "Invalid credentials.")
    return render(request, 'accounts/login.html')

# def logout_view(request):
#     logout(request)
#     messages.success(request, "You have successfully logged out.")
#     return redirect('login')  # or wherever you want to redirect