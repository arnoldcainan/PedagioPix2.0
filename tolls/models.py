from django.db import models
from django.utils import timezone


class CategoriaVeiculo(models.TextChoices):
    MOTO = 'MOTO', 'Moto'
    CARRO = 'CARRO', 'Carro'
    CAMINHAO = 'CAMINHAO', 'Caminhão'


class Passagem(models.Model):
    # O id (Primary Key) é criado automaticamente pelo Django
    placa = models.CharField(max_length=7, verbose_name="Placa do Veículo")
    categoria = models.CharField(
        max_length=10,
        choices=CategoriaVeiculo.choices,
        verbose_name="Categoria"
    )
    valor = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Valor Cobrado")
    data_registro = models.DateTimeField(auto_now_add=True, verbose_name="Data da Passagem")

    class Meta:
        verbose_name = "Passagem"
        verbose_name_plural = "Passagens"
        ordering = ['-data_registro']

    def __str__(self):
        return f"{self.placa} - {self.get_categoria_display()} (R$ {self.valor})"


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