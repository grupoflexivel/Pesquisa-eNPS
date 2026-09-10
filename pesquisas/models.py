import re
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def somente_digitos(valor):
    return re.sub(r'\D', '', valor or '')


def validar_cpf(valor):
    cpf = somente_digitos(valor)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValidationError('Informe um CPF válido com 11 dígitos.')
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[tamanho]):
            raise ValidationError('Informe um CPF válido.')


class User(AbstractUser):
    """Usuário administrativo; colaboradores não precisam de login."""

    class Meta:
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'


class Colaborador(models.Model):
    nome = models.CharField(max_length=200)
    cpf = models.CharField(max_length=11, unique=True, validators=[validar_cpf])
    ativo = models.BooleanField(default=True)

    data_criacao = models.DateTimeField(default=timezone.now)
    data_inativacao = models.DateTimeField(null=True, blank=True)
    data_ativacao = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ('nome',)

    def clean(self):
        super().clean()
        self.cpf = somente_digitos(self.cpf)
        validar_cpf(self.cpf)

    def save(self, *args, **kwargs):
        self.cpf = somente_digitos(self.cpf)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Pesquisa(models.Model):
    titulo = models.CharField(max_length=200)
    data_inicio = models.DateTimeField()
    data_final = models.DateTimeField()
    link_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='pesquisas_criadas')

    class Meta:
        ordering = ('-data_inicio',)

    @property
    def edicao_bloqueada(self):
        return timezone.now() >= self.data_inicio

    @property
    def vigente(self):
        agora = timezone.now()
        return self.data_inicio <= agora <= self.data_final

    def clean(self):
        super().clean()
        if self.data_inicio and self.data_final and self.data_final <= self.data_inicio:
            raise ValidationError({'data_final': 'A data final deve ser posterior à data inicial.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)
    
    def __str__(self):
        return self.titulo


class Pergunta(models.Model):
    class TipoResposta(models.TextChoices):
        TEXTO = 'TEXTO', 'Texto'
        NOTA_0_10 = 'NOTA_0_10', 'Nota de 0 a 10'

    pesquisa = models.ForeignKey(Pesquisa, on_delete=models.CASCADE, related_name='perguntas')
    texto_pergunta = models.TextField()
    tipo_resposta = models.CharField(max_length=12, choices=TipoResposta.choices)
    ordem = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ('ordem', 'pk')
        constraints = [models.UniqueConstraint(fields=('pesquisa', 'ordem'), name='pergunta_ordem_unica')]

    def clean(self):
        super().clean()
        if self.pesquisa_id and self.pesquisa.edicao_bloqueada:
            raise ValidationError('Perguntas de uma pesquisa iniciada não podem ser alteradas.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f'{self.ordem}. {self.texto_pergunta[:80]}'


class RespostaPesquisa(models.Model):
    pesquisa = models.ForeignKey(Pesquisa, on_delete=models.CASCADE, related_name='respostas')
    data_resposta = models.DateTimeField(default=timezone.now, editable=False)
    hash_cpf_respondente = models.CharField(max_length=64, editable=False)

    class Meta:
        ordering = ('-data_resposta',)
        constraints = [models.UniqueConstraint(fields=('pesquisa', 'hash_cpf_respondente'), name='resposta_unica_por_cpf_e_pesquisa')]

    def __str__(self):
        return f'Resposta anônima #{self.pk} - {self.pesquisa}'


class DetalheResposta(models.Model):
    resposta_pesquisa = models.ForeignKey(RespostaPesquisa, on_delete=models.CASCADE, related_name='detalhes')
    pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE, related_name='detalhes') 
    valor_texto = models.TextField(blank=True, null=True)
    valor_inteiro = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(10)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('resposta_pesquisa', 'pergunta'), name='uma_resposta_por_pergunta'),
            models.CheckConstraint(
                condition=(models.Q(valor_texto__isnull=False, valor_inteiro__isnull=True) | models.Q(valor_texto__isnull=True, valor_inteiro__isnull=False)),
                name='detalhe_exatamente_um_valor',
            ),
        ]

    def clean(self):
        super().clean()
        if self.pergunta_id:
            if self.pergunta.tipo_resposta == Pergunta.TipoResposta.TEXTO:
                if not (self.valor_texto or '').strip() or self.valor_inteiro is not None:
                    raise ValidationError('Esta pergunta exige uma resposta em texto.')
            elif self.valor_inteiro is None or self.valor_texto is not None:
                raise ValidationError('Esta pergunta exige uma nota de 0 a 10.')
        if self.resposta_pesquisa_id and self.pergunta_id and self.resposta_pesquisa.pesquisa_id != self.pergunta.pesquisa_id:
            raise ValidationError('A pergunta não pertence à pesquisa respondida.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Detalhe #{self.pk}'