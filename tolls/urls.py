from django.urls import path
from . import views

urlpatterns = [
    path('cobranca-pix/', views.gerar_cobranca_pix, name='gerar_cobranca_pix'),
    path('listar-pix/', views.listar_pix, name='listar_pix'),
    path('consulta/', views.consulta_publica, name='consulta_publica'),
]