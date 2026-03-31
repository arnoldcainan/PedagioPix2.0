from django.contrib import admin
from .models import Passagem, CobrancaPix

@admin.register(Passagem)
class PassagemAdmin(admin.ModelAdmin):
    list_display = ('placa', 'categoria', 'valor', 'data_registro')
    search_fields = ('placa',)
    list_filter = ('categoria', 'data_registro')

@admin.register(CobrancaPix)
class CobrancaPixAdmin(admin.ModelAdmin):
    list_display = ('txid', 'get_placa', 'pago', 'data_criacao', 'data_expiracao')
    search_fields = ('txid', 'passagem__placa')
    list_filter = ('pago', 'data_criacao')

    # Método customizado para exibir a placa da passagem relacionada
    def get_placa(self, obj):
        return obj.passagem.placa
    get_placa.short_description = 'Placa'