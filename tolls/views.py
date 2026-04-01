from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncDate
from django.db.models import Sum

from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from .models import Passagem, CobrancaPix, CategoriaTarifa
from .services import BancoBrasilPixService
import re

from decimal import Decimal


@login_required
def gerar_cobranca_pix(request):
    categorias = CategoriaTarifa.objects.filter(ativo=True).order_by('id')

    # Identifica o valor do eixo avulso para calcular o desconto (CAT 15)
    categoria_eixo = categorias.filter(tipo_cobranca='POR_EIXO').first()
    valor_eixo_suspenso = categoria_eixo.valor_base if categoria_eixo else Decimal('8.40')

    if request.method == 'POST':
        placa = request.POST.get('placa')
        categoria_id = request.POST.get('categoria_id')

        # Captura os dois tipos de inputs da tela
        qtd_eixos = int(request.POST.get('qtd_eixos', 1))
        eixos_suspensos = int(request.POST.get('eixos_suspensos', 0))

        if not placa or not categoria_id:
            messages.error(request, 'Placa e Categoria são obrigatórios.')
            return redirect('gerar_cobranca_pix')

        placa_formatada = placa.upper().strip()
        padrao_placa = re.compile(r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$')
        if not padrao_placa.match(placa_formatada):
            messages.error(request, f'A placa "{placa}" é inválida.')
            return redirect('gerar_cobranca_pix')

        try:
            categoria = CategoriaTarifa.objects.get(id=categoria_id)
        except CategoriaTarifa.DoesNotExist:
            messages.error(request, 'Categoria não encontrada.')
            return redirect('gerar_cobranca_pix')

        # =========================================================
        # MOTOR DE CÁLCULO DINÂMICO (Com Eixo Suspenso)
        # =========================================================
        if categoria.tipo_cobranca == 'POR_EIXO':
            valor_final = categoria.valor_base * qtd_eixos
            eixos_cobrados_reais = qtd_eixos
        else:
            # Calcula o desconto baseado em quantos eixos foram suspensos
            valor_desconto = Decimal(str(eixos_suspensos)) * valor_eixo_suspenso
            valor_final = categoria.valor_base - valor_desconto

            # Estima quantos eixos foram efetivamente cobrados para o relatório
            eixos_base_estimados = int(categoria.valor_base / valor_eixo_suspenso)
            eixos_cobrados_reais = eixos_base_estimados - eixos_suspensos if eixos_base_estimados > 0 else 1
        # =========================================================

        pix_existente = CobrancaPix.objects.filter(
            passagem__placa=placa_formatada, pago=False, data_expiracao__gt=timezone.now()
        ).first()

        if pix_existente:
            messages.info(request, f'Cobrança ativa encontrada para {placa_formatada}.')
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
                    eixos_cobrados=eixos_cobrados_reais,  # Salva a quantidade real reduzida!
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
            return render(request, 'pagamento_pix.html', context)

        except Exception as e:
            messages.error(request, f'Erro ao processar cobrança: {str(e)}')
            return redirect('gerar_cobranca_pix')

    # Passamos o valor do eixo para o JavaScript usar na tela
    return render(request, 'admin_cobranca_pix.html', {
        'categorias': categorias,
        'valor_eixo_suspenso': valor_eixo_suspenso
    })


@login_required
def dashboard_gerencial(request):
    agora = timezone.now()
    sete_dias_atras = agora - timedelta(days=7)

    # KPIs Básicos (Mantendo o que já tínhamos)
    pagos = CobrancaPix.objects.filter(pago=True)
    faturamento = pagos.aggregate(total=Sum('passagem__valor'))['total'] or 0.00
    qtd_pagos = pagos.count()
    qtd_evasoes = CobrancaPix.objects.filter(pago=False, data_expiracao__lte=agora).count()

    # --- DADOS PARA O GRÁFICO (Fluxo de 7 dias) ---
    vendas_diarias = CobrancaPix.objects.filter(
        pago=True,
        data_criacao__gte=sete_dias_atras
    ).annotate(
        dia=TruncDate('data_criacao')
    ).values('dia').annotate(
        total=Sum('passagem__valor')
    ).order_by('dia')

    # Formatando para o JavaScript (Listas de strings e números)
    labels_grafico = [v['dia'].strftime("%d/%m") for v in vendas_diarias]
    dados_grafico = [float(v['total']) for v in vendas_diarias]

    context = {
        'faturamento': faturamento,
        'qtd_pagos': qtd_pagos,
        'qtd_evasoes': qtd_evasoes,
        'labels_grafico': labels_grafico,
        'dados_grafico': dados_grafico,
        'ultimas_evasoes': CobrancaPix.objects.filter(pago=False, data_expiracao__lte=agora).order_by(
            '-data_expiracao')[:5]
    }

    return render(request, 'admin_dashboard.html', context)


@login_required
def relatorio_financeiro(request):
    # Captura filtros da URL
    status = request.GET.get('status')
    placa = request.GET.get('placa')

    pix_list = CobrancaPix.objects.select_related('passagem', 'passagem__categoria').all()

    if status == 'pago':
        pix_list = pix_list.filter(pago=True)
    elif status == 'pendente':
        pix_list = pix_list.filter(pago=False, data_expiracao__gt=timezone.now())
    elif status == 'evasao':
        pix_list = pix_list.filter(pago=False, data_expiracao__lte=timezone.now())

    if placa:
        pix_list = pix_list.filter(passagem__placa__icontains=placa.upper())

    return render(request, 'relatorio_financeiro.html', {'pix_list': pix_list})


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