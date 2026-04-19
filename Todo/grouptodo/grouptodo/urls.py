"""
URL configuration for grouptodo project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from tasks import views as task_views
from tasks.forms import LoginForm

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- Authentication URLs (Project Level) ---
    path('register/', task_views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=LoginForm
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        http_method_names = ['get', 'post', 'options']
    ), name='logout'),

    # --- App URLs ---
    # The namespace will be loaded from 'tasks/urls.py' (via app_name)
    path('', include('tasks.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


