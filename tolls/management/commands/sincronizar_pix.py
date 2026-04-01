import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from tolls.models import CobrancaPix
from tolls.services import BancoBrasilPixService


class Command(BaseCommand):
    help = 'Consulta o Banco do Brasil para verificar se os PIX pendentes foram pagos'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING(f'[{timezone.now()}] Iniciando varredura de PIX pendentes...'))

        agora = timezone.now()

        # Busca no banco APENAS os que não estão pagos e que ainda não venceram
        pendentes = CobrancaPix.objects.filter(pago=False, data_expiracao__gt=agora)
        qtd = pendentes.count()

        if qtd == 0:
            self.stdout.write(self.style.SUCCESS('Nenhum PIX pendente no momento. Tudo limpo!'))
            return

        self.stdout.write(f'Encontrados {qtd} PIX pendentes para consulta.')

        bb_service = BancoBrasilPixService()
        atualizados = 0

        for pix in pendentes:
            try:
                # Chama a API do Banco do Brasil
                resposta = bb_service.consultar_pix(pix.txid)
                status_bb = resposta.get('status')  # Geralmente retorna 'ATIVA' ou 'CONCLUIDA'

                if status_bb == 'CONCLUIDA':
                    pix.pago = True
                    pix.save()
                    atualizados += 1
                    self.stdout.write(self.style.SUCCESS(f'✅ TXID {pix.txid} PAGO! Atualizado no banco.'))
                else:
                    self.stdout.write(f'⏳ TXID {pix.txid} continua pendente (Status: {status_bb}).')

                # Dá um pequeno respiro para não derrubar a API do BB (Rate Limit)
                time.sleep(1)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Erro ao consultar TXID {pix.txid}: {str(e)}'))

        self.stdout.write(
            self.style.SUCCESS(f'[{timezone.now()}] Varredura concluída. {atualizados} PIX atualizados para PAGO.'))