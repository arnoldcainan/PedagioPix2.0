from django.contrib import admin
from .models import Passagem, CobrancaPix, CategoriaTarifa

@admin.register(CategoriaTarifa)
class CategoriaTarifaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descricao', 'tipo_cobranca', 'valor_base', 'ativo')
    list_editable = ('valor_base', 'ativo') # Permite editar o valor direto na listagem!
    search_fields = ('codigo', 'descricao')

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