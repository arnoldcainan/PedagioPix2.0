from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from tolls.views import home

urlpatterns = [
    path('admin/', admin.site.urls),

    # Autenticação (Nativas do Django)
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Encaminhamento para o App de Arrecadação (Tolls)
    path('arrecadacao/', include('tolls.urls')),

    # Rota Raiz (Home) - Geralmente vinculada ao app principal ou Dashboard
    path('', home, name='home'),
]