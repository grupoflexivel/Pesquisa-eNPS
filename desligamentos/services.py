from .models import Desligamento


def registrar_desligamento_pendente(colaborador, iniciativa, formulario, usuario):
    """Cria o card de desligamento na coluna Pendentes para o colaborador inativado."""
    return Desligamento.objects.create(
        colaborador=colaborador,
        formulario=formulario,
        iniciativa=iniciativa,
        status=Desligamento.Status.PENDENTE,
        criado_por=usuario,
    )


def cancelar_desligamentos_abertos(colaborador):
    """Remove pendências de desligamento em aberto quando o colaborador é reativado."""
    Desligamento.objects.filter(
        colaborador=colaborador,
        status__in=(Desligamento.Status.PENDENTE, Desligamento.Status.AGUARDANDO_RESPOSTA),
    ).delete()
