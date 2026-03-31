from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from .models import Passagem, CobrancaPix, CategoriaTarifa
from .services import BancoBrasilPixService
import re


@login_required
def gerar_cobranca_pix(request):
    # Pega todas as categorias ativas no banco para desenhar a tela
    categorias = CategoriaTarifa.objects.filter(ativo=True).order_by('id')

    if request.method == 'POST':
        placa = request.POST.get('placa')
        categoria_id = request.POST.get('categoria_id')
        qtd_eixos = int(request.POST.get('qtd_eixos', 1))

        if not placa or not categoria_id:
            messages.error(request, 'Placa e Categoria são obrigatórios.')
            return redirect('gerar_cobranca_pix')

        placa_formatada = placa.upper().strip()

        # Validação Regex de Placa
        padrao_placa = re.compile(r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$')
        if not padrao_placa.match(placa_formatada):
            messages.error(request, f'A placa "{placa}" é inválida. Use o formato ABC1234 ou ABC1D23.')
            return redirect('gerar_cobranca_pix')

        # Busca a categoria selecionada no banco
        try:
            categoria = CategoriaTarifa.objects.get(id=categoria_id)
        except CategoriaTarifa.DoesNotExist:
            messages.error(request, 'Categoria não encontrada no sistema.')
            return redirect('gerar_cobranca_pix')

        # =========================================================
        # MOTOR DE CÁLCULO DINÂMICO
        # Se for CAT 15 (POR EIXO), multiplica. Se for normal, pega o base.
        if categoria.tipo_cobranca == 'POR_EIXO':
            valor_final = categoria.valor_base * qtd_eixos
        else:
            valor_final = categoria.valor_base
            qtd_eixos = 1  # Categoria normal conta como "1 passagem"
        # =========================================================

        # Trava de Idempotência (Agora buscando pela Foreign Key)
        pix_existente = CobrancaPix.objects.filter(
            passagem__placa=placa_formatada,
            pago=False,
            data_expiracao__gt=timezone.now()
        ).first()

        if pix_existente:
            messages.info(request, f'Já existe uma cobrança ativa para a placa {placa_formatada}.')
            context = {
                'qr_code': {
                    'encodedImage': pix_existente.qr_code_base64,
                    'payload': pix_existente.payload,
                    'expirationDate': pix_existente.data_expiracao.strftime("%d/%m/%Y %H:%M:%S"),
                    'placa': pix_existente.passagem.placa,
                    'valor': pix_existente.passagem.valor
                }
            }
            return render(request, 'pagamento_pix.html', context)

        try:
            with transaction.atomic():
                passagem = Passagem.objects.create(
                    placa=placa_formatada,
                    categoria=categoria,
                    eixos_cobrados=qtd_eixos,
                    valor=valor_final
                )

                bb_service = BancoBrasilPixService()
                pix_data = bb_service.criar_cobranca(passagem)

                CobrancaPix.objects.create(
                    passagem=passagem,
                    txid=pix_data['txid'],
                    payload=pix_data['payload'],
                    qr_code_base64=pix_data['qr_code_base64'],
                    data_expiracao=pix_data['data_expiracao']
                )

            context = {
                'qr_code': {
                    'encodedImage': pix_data['qr_code_base64'],
                    'payload': pix_data['payload'],
                    'expirationDate': pix_data['data_expiracao'].strftime("%d/%m/%Y %H:%M:%S"),
                    'placa': placa_formatada,
                    'valor': valor_final
                }
            }
            messages.success(request, 'Nova cobrança gerada com sucesso!')
            return render(request, 'pagamento_pix.html', context)

        except Exception as e:
            messages.error(request, f'Erro ao processar cobrança: {str(e)}')
            return redirect('gerar_cobranca_pix')

    # Para requisições GET, envia as categorias pro HTML desenhar os botões
    return render(request, 'admin_cobranca_pix.html', {'categorias': categorias})


@login_required
def listar_pix(request):
    # Pega todas as cobranças, usando select_related para otimizar a query no banco de dados
    pix_list = CobrancaPix.objects.select_related('passagem').all()
    return render(request, 'admin_listar_pix.html', {'pix_list': pix_list})

def home(request):
    # Aqui você poderia buscar dados reais do banco, como total de AITs do dia
    return render(request, 'home.html')


def consulta_publica(request):
    context = {}

    if request.method == 'POST':
        placa_crua = request.POST.get('placa', '')

        # Limpa tudo que não for letra ou número e joga para maiúsculo
        placa_formatada = re.sub(r'[^A-Z0-9]', '', placa_crua.upper())

        # Validação Regex
        padrao_placa = re.compile(r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$')

        if not padrao_placa.match(placa_formatada):
            messages.error(request, 'Placa inválida. Digite no formato padrão (ABC1234) ou Mercosul (ABC1D23).')
        else:
            # Busca cobranças pendentes e que ainda não venceram para essa placa
            pix_pendente = CobrancaPix.objects.filter(
                passagem__placa=placa_formatada,
                pago=False,
                data_expiracao__gt=timezone.now()
            ).first()

            if pix_pendente:
                context['pix'] = pix_pendente
                context['placa_pesquisada'] = placa_formatada
            else:
                messages.info(request, f'Nenhuma cobrança pendente encontrada para a placa {placa_formatada}.')
                context['placa_pesquisada'] = placa_formatada

    return render(request, 'consulta_publica.html', context)