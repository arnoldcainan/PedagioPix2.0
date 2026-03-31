from django.db import models
from django.utils import timezone

class TipoCobranca(models.TextChoices):
    FIXA = 'FIXA', 'Tarifa Fixa'
    POR_EIXO = 'POR_EIXO', 'Multiplicado por Eixo'

class CategoriaTarifa(models.Model):
    codigo = models.CharField(max_length=10, unique=True, verbose_name="Cód. (Ex: CAT 1)")
    descricao = models.CharField(max_length=100, verbose_name="Descrição (Ex: Passeio)",blank=True, null=True)
    tipo_cobranca = models.CharField(max_length=10, choices=TipoCobranca.choices, default=TipoCobranca.FIXA)
    valor_base = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Valor Base (R$)")
    icone = models.CharField(max_length=50, default="fa-solid fa-car", help_text="Classe do FontAwesome")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoria de Tarifa"
        verbose_name_plural = "Categorias de Tarifas"
        ordering = ['id']

    def __str__(self):
        return f"{self.codigo} - {self.descricao} (R$ {self.valor_base})"


class Passagem(models.Model):
    placa = models.CharField(max_length=7, verbose_name="Placa do Veículo")

    # A categoria agora é uma chave estrangeira apontando para a nova tabela
    categoria = models.ForeignKey(CategoriaTarifa, on_delete=models.PROTECT, verbose_name="Categoria")

    # Campo extra para registrar quantos eixos foram cobrados na CAT 15
    eixos_cobrados = models.IntegerField(default=1, verbose_name="Eixos Cobrados")

    valor = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Valor Cobrado")
    data_registro = models.DateTimeField(auto_now_add=True, verbose_name="Data da Passagem")

    class Meta:
        verbose_name = "Passagem"
        verbose_name_plural = "Passagens"
        ordering = ['-data_registro']

    def __str__(self):
        return f"{self.placa} - {self.categoria.codigo} (R$ {self.valor})"


class CobrancaPix(models.Model):
    # Relacionamento 1 para 1: Uma passagem tem uma cobrança PIX.
    passagem = models.OneToOneField(
        Passagem,
        on_delete=models.CASCADE,
        related_name='pix',
        verbose_name="Passagem Referência"
    )

    txid = models.CharField(max_length=255, unique=True, verbose_name="TXID")
    payload = models.TextField(verbose_name="PIX Copia e Cola")
    qr_code_base64 = models.TextField(verbose_name="QR Code (Base64)")
    data_expiracao = models.DateTimeField(verbose_name="Data de Expiração")
    pago = models.BooleanField(default=False, verbose_name="Pagamento Confirmado")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Cobrança PIX"
        verbose_name_plural = "Cobranças PIX"
        ordering = ['-data_criacao']

    def is_expired(self):
        return timezone.now() > self.data_expiracao

    def __str__(self):
        status = "PAGO" if self.pago else "PENDENTE"
        return f"PIX {self.txid} - {status}"