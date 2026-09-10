from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError

from .forms import ColaboradorForm, PerguntaFormSet, PesquisaForm, ResponderPerguntaForm, ValidarCPFForm
from .models import Colaborador, DetalheResposta, Empresa, Pergunta, Pesquisa, RespostaPesquisa
from .services import gerar_hash_cpf


staff_required = user_passes_test(lambda user: user.is_authenticated and user.is_staff)


def _status_pesquisa(pesquisa):
    agora = timezone.now()
    if agora < pesquisa.data_inicio:
        return 'Agendada'
    if agora > pesquisa.data_final:
        return 'Encerrada'
    return 'Em andamento'


@staff_required
def dashboard(request):
    contexto = {
        'total_colaboradores': Colaborador.objects.filter(ativo=True).count(),
        'total_pesquisas': Pesquisa.objects.count(),
        'total_respostas': RespostaPesquisa.objects.count(),
        'pesquisas': Pesquisa.objects.annotate(total_respostas=Count('respostas'))[:8],
    }
    return render(request, 'pesquisas/dashboard.html', contexto)


@staff_required
def colaborador_lista(request):
    termo = request.GET.get('q', '').strip()
    empresa_id = request.GET.get('empresa', '').strip()
    status = request.GET.get('status', '').strip()
    
    colaboradores = Colaborador.objects.select_related('empresa')
    
    if termo:
        colaboradores = colaboradores.filter(
            Q(nome__icontains=termo) | Q(cpf__icontains=termo) | Q(empresa__nome__icontains=termo)
        )
        
    if empresa_id:
        colaboradores = colaboradores.filter(empresa_id=empresa_id)
        
    if status == 'ativo':
        colaboradores = colaboradores.filter(ativo=True)
    elif status == 'inativo':
        colaboradores = colaboradores.filter(ativo=False)

    return render(request, 'pesquisas/colaborador_lista.html', {
        'colaboradores': colaboradores,
        'termo': termo,
        'empresas': Empresa.objects.all(),
        'empresa_selecionada': empresa_id,
        'status_selecionado': status,
    })


@staff_required
def colaborador_criar(request):
    form = ColaboradorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        colaborador = form.save(commit=False)
        colaborador.data_ativacao = timezone.now()
        colaborador.save()
        messages.success(request, 'Colaborador cadastrado com sucesso.')
        return redirect('pesquisas:colaborador_lista')
    return render(request, 'pesquisas/colaborador_form.html', {'form': form})


@staff_required
def colaborador_editar(request, pk):
    colaborador = get_object_or_404(Colaborador, pk=pk)
    estava_ativo = colaborador.ativo
    form = ColaboradorForm(request.POST or None, instance=colaborador)
    if request.method == 'POST' and form.is_valid():
        colaborador = form.save(commit=False)
        if estava_ativo and not colaborador.ativo:
            colaborador.data_inativacao = timezone.now()
        elif not estava_ativo and colaborador.ativo:
            colaborador.data_inativacao = None
            colaborador.data_ativacao = timezone.now()
        colaborador.save()
        messages.success(request, 'Colaborador atualizado com sucesso.')
        return redirect('pesquisas:colaborador_lista')
    return render(request, 'pesquisas/colaborador_form.html', {
        'form': form,
        'colaborador': colaborador,
    })


@staff_required
@require_POST
def colaborador_alterar_status(request, pk):
    colaborador = get_object_or_404(Colaborador, pk=pk)
    colaborador.ativo = not colaborador.ativo
    
    agora = timezone.now()
    if not colaborador.ativo:
        colaborador.data_inativacao = agora
    else:
        colaborador.data_inativacao = None
        colaborador.data_ativacao = agora
        
    colaborador.save()
    status = 'ativo' if colaborador.ativo else 'inativo'
    messages.success(request, f'{colaborador.nome} agora está {status}.')
    return redirect('pesquisas:colaborador_lista')

@staff_required
def pesquisa_lista(request):
    pesquisas = list(Pesquisa.objects.select_related('criado_por'))
    for pesquisa in pesquisas:
        pesquisa.status_exibicao = _status_pesquisa(pesquisa)
    return render(request, 'pesquisas/pesquisa_lista.html', {'pesquisas': pesquisas})


def _salvar_pesquisa(request, instance=None):
    bloquear_perguntas = instance.edicao_bloqueada if instance else False

    form = PesquisaForm(request.POST or None, instance=instance)
    
    if bloquear_perguntas:
        formset = PerguntaFormSet(None, instance=instance, prefix='perguntas')
        for q_form in formset.forms:
            for field in q_form.fields.values():
                field.widget.attrs['disabled'] = 'disabled'
    else:
        formset = PerguntaFormSet(request.POST or None, instance=instance, prefix='perguntas')

    if request.method == 'POST':
        form_valido = form.is_valid()
        formset_valido = True if bloquear_perguntas else formset.is_valid()

        if form_valido and formset_valido:
            with transaction.atomic():
                pesquisa = form.save(commit=False)
                if not pesquisa.pk:
                    pesquisa.criado_por = request.user
                pesquisa.save()
                
                if not bloquear_perguntas:
                    formset.instance = pesquisa
                    formset.save()

            messages.success(request, 'Pesquisa salva com sucesso.')
            return redirect('pesquisas:pesquisa_lista')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erro no campo {field}: {error}")
            if not bloquear_perguntas:
                for q_form in formset:
                    for field, errors in q_form.errors.items():
                        for error in errors:
                            messages.error(request, f"Erro na pergunta ({field}): {error}")

    return render(request, 'pesquisas/pesquisa_form.html', {
        'form': form, 
        'formset': formset, 
        'pesquisa': instance,
        'bloquear_perguntas': bloquear_perguntas
    })


@staff_required
def pesquisa_criar(request):
    return _salvar_pesquisa(request)


@staff_required
def pesquisa_editar(request, pk):
    pesquisa = get_object_or_404(Pesquisa, pk=pk)
    
    if pesquisa.edicao_bloqueada and request.method == 'GET':
        messages.warning(request, 'A edição das perguntas está bloqueada porque a pesquisa já começou. Você pode alterar apenas as informações gerais.')

    return _salvar_pesquisa(request, pesquisa)


@staff_required
@require_POST
def pesquisa_excluir(request, pk):
    pesquisa = get_object_or_404(Pesquisa, pk=pk)
    try:
        pesquisa.delete()
        messages.success(request, 'Pesquisa excluída com sucesso.')
    except Exception as e:
        messages.error(request, f'Erro ao excluir pesquisa: {str(e)}')
    return redirect('pesquisas:pesquisa_lista')


@staff_required
def resultados(request, pk):
    pesquisa = get_object_or_404(Pesquisa, pk=pk)
    empresas = Empresa.objects.all()
    empresa_selecionada = None
    empresa_id = request.GET.get('empresa', '').strip()
    if empresa_id:
        try:
            empresa_selecionada = get_object_or_404(Empresa, pk=int(empresa_id))
        except (TypeError, ValueError):
            raise Http404('Empresa inválida.')

    pergunta_enps = pesquisa.perguntas.filter(tipo_resposta=Pergunta.TipoResposta.NOTA_0_10).first()
    
    # Lógica de contagem precisa considerando segundos e horário de ativação/inativação:
    colaboradores_elegiveis = Colaborador.objects.filter(
        data_criacao__lte=pesquisa.data_final
    ).exclude(
        Q(data_ativacao__gt=pesquisa.data_final)
    ).exclude(
        Q(ativo=False) & Q(data_inativacao__lt=pesquisa.data_inicio)
    )
    if empresa_selecionada:
        colaboradores_elegiveis = colaboradores_elegiveis.filter(empresa=empresa_selecionada)

    ativos = colaboradores_elegiveis.count()
    hashes_elegiveis = [
        gerar_hash_cpf(cpf)
        for cpf in colaboradores_elegiveis.values_list('cpf', flat=True).iterator()
    ]
    respostas = pesquisa.respostas.filter(hash_cpf_respondente__in=hashes_elegiveis)

    respondentes = respostas.count()

    promotores = neutros = detratores = 0
    if pergunta_enps:
        notas = DetalheResposta.objects.filter(
            pergunta=pergunta_enps,
            resposta_pesquisa__in=respostas,
        )
        promotores = notas.filter(valor_inteiro__gte=9).count()
        neutros = notas.filter(valor_inteiro__range=(7, 8)).count()
        detratores = notas.filter(valor_inteiro__range=(0, 6)).count()
        
    percentual = (respondentes / ativos * 100) if ativos else 0
    enps = ((promotores - detratores) / respondentes * 100) if respondentes else 0

    perguntas_demais = []
    qs_perguntas = pesquisa.perguntas.all()
    if pergunta_enps:
        qs_perguntas = qs_perguntas.exclude(pk=pergunta_enps.pk)

    for p in qs_perguntas:
        detalhes = p.detalhes.select_related('resposta_pesquisa').filter(
            resposta_pesquisa__in=respostas,
        )
        media = None
        if p.tipo_resposta == Pergunta.TipoResposta.NOTA_0_10 and detalhes.exists():
            soma = sum(d.valor_inteiro for d in detalhes if d.valor_inteiro is not None)
            media = soma / detalhes.count()
            
        perguntas_demais.append({
            'pergunta': p,
            'detalhes': detalhes,
            'media': media,
        })

    return render(request, 'pesquisas/resultados.html', {
        'pesquisa': pesquisa, 'pergunta_enps': pergunta_enps, 'ativos': ativos,
        'respondentes': respondentes, 'percentual': percentual, 'promotores': promotores,
        'neutros': neutros, 'detratores': detratores, 'enps': enps,
        'perguntas_demais': perguntas_demais,
        'empresas': empresas, 'empresa_selecionada': empresa_selecionada,
    })


def _pesquisa_disponivel(link_uuid):
    pesquisa = get_object_or_404(Pesquisa, link_uuid=link_uuid)
    if not pesquisa.vigente:
        return pesquisa, 'Esta pesquisa ainda não começou ou já foi encerrada.'
    if pesquisa.perguntas.count() < 3:
        return pesquisa, 'Esta pesquisa não está disponível.'
    return pesquisa, None


def validar_participante(request, link_uuid):
    pesquisa, indisponivel = _pesquisa_disponivel(link_uuid)
    form = ValidarCPFForm(request.POST or None)
    erro = indisponivel
    if request.method == 'POST' and not indisponivel and form.is_valid():
        cpf = form.cleaned_data['cpf']
        if not Colaborador.objects.filter(cpf=cpf, ativo=True).exists():
            erro = 'CPF não encontrado ou colaborador inativo.'
        else:
            hash_cpf = gerar_hash_cpf(cpf)
            if pesquisa.respostas.filter(hash_cpf_respondente=hash_cpf).exists():
                erro = 'Uma resposta já foi enviada para este CPF.'
            else:
                request.session[f'pesquisa_auth_{link_uuid}'] = hash_cpf
                request.session[f'pesquisa_respostas_{link_uuid}'] = {}
                return redirect('pesquisas:responder_etapa', link_uuid=link_uuid, etapa=1)
    return render(request, 'pesquisas/validar_cpf.html', {
        'pesquisa': pesquisa, 'form': form, 'erro': erro, 'hide_sidebar': True,
    })


def responder_etapa(request, link_uuid, etapa):
    pesquisa, indisponivel = _pesquisa_disponivel(link_uuid)
    hash_cpf = request.session.get(f'pesquisa_auth_{link_uuid}')
    if indisponivel or not hash_cpf:
        messages.error(request, indisponivel or 'Valide seu CPF antes de responder.')
        return redirect('pesquisas:responder', link_uuid=link_uuid)
    if pesquisa.respostas.filter(hash_cpf_respondente=hash_cpf).exists():
        request.session[f'pesquisa_concluida_{link_uuid}'] = True
        return redirect('pesquisas:agradecimento', link_uuid=link_uuid)
    perguntas = list(pesquisa.perguntas.all())
    if etapa < 1 or etapa > len(perguntas):
        raise Http404
    pergunta = perguntas[etapa - 1]
    respostas_key = f'pesquisa_respostas_{link_uuid}'
    respostas = request.session.get(respostas_key, {})
    for indice, anterior in enumerate(perguntas[:etapa - 1], start=1):
        if str(anterior.pk) not in respostas:
            return redirect('pesquisas:responder_etapa', link_uuid=link_uuid, etapa=indice)
    form = ResponderPerguntaForm(pergunta, request.POST or None, initial={'valor': respostas.get(str(pergunta.pk))})
    if request.method == 'POST' and form.is_valid():
        respostas[str(pergunta.pk)] = form.cleaned_data['valor']
        request.session[respostas_key] = respostas
        if etapa < len(perguntas):
            return redirect('pesquisas:responder_etapa', link_uuid=link_uuid, etapa=etapa + 1)
        try:
            with transaction.atomic():
                resposta = RespostaPesquisa.objects.create(pesquisa=pesquisa, hash_cpf_respondente=hash_cpf)
                for item in perguntas:
                    valor = respostas.get(str(item.pk))
                    DetalheResposta.objects.create(
                        resposta_pesquisa=resposta, pergunta=item,
                        valor_texto=valor if item.tipo_resposta == Pergunta.TipoResposta.TEXTO else None,
                        valor_inteiro=valor if item.tipo_resposta == Pergunta.TipoResposta.NOTA_0_10 else None,
                    )
        except IntegrityError:
            pass
        request.session.pop(f'pesquisa_auth_{link_uuid}', None)
        request.session.pop(respostas_key, None)
        request.session[f'pesquisa_concluida_{link_uuid}'] = True
        return redirect('pesquisas:agradecimento', link_uuid=link_uuid)
    return render(request, 'pesquisas/responder_etapa.html', {
        'pesquisa': pesquisa, 'pergunta': pergunta, 'form': form, 'etapa': etapa,
        'total': len(perguntas), 'progresso': int(etapa / len(perguntas) * 100), 'hide_sidebar': True,
    })


def agradecimento(request, link_uuid):
    pesquisa = get_object_or_404(Pesquisa, link_uuid=link_uuid)
    if not request.session.get(f'pesquisa_concluida_{link_uuid}', False):
        return redirect('pesquisas:responder', link_uuid=link_uuid)
    return render(request, 'pesquisas/agradecimento.html', {'pesquisa': pesquisa, 'hide_sidebar': True})
