from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Colaborador, DetalheResposta, Pergunta, Pesquisa, RespostaPesquisa, User, validar_cpf
from .services import gerar_hash_cpf


CPF_VALIDO = '52998224725'


@override_settings(SECRET_SALT='segredo-de-teste')
class DominioTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('gestor', password='senha', is_staff=True)

    def pesquisa(self, inicio=None):
        return Pesquisa.objects.create(
            titulo='Clima',
            data_inicio=inicio or timezone.now() + timedelta(hours=1),
            data_final=timezone.now() + timedelta(days=2),
            criado_por=self.staff,
        )

    def test_valida_cpf_e_hash_nao_expoe_cpf(self):
        validar_cpf(CPF_VALIDO)
        hash_cpf = gerar_hash_cpf(CPF_VALIDO)
        self.assertEqual(len(hash_cpf), 64)
        self.assertNotIn(CPF_VALIDO, hash_cpf)
        with self.assertRaises(ValidationError):
            validar_cpf('11111111111')

    def test_pesquisa_iniciada_nao_pode_ser_editada(self):
        pesquisa = self.pesquisa()
        Pesquisa.objects.filter(pk=pesquisa.pk).update(data_inicio=timezone.now() - timedelta(minutes=1))
        pesquisa.refresh_from_db()
        pesquisa.titulo = 'Alterada'
        with self.assertRaises(ValidationError):
            pesquisa.save()

    def test_constraint_impede_resposta_duplicada(self):
        pesquisa = self.pesquisa()
        RespostaPesquisa.objects.create(pesquisa=pesquisa, hash_cpf_respondente='a' * 64)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RespostaPesquisa.objects.create(pesquisa=pesquisa, hash_cpf_respondente='a' * 64)


@override_settings(SECRET_SALT='segredo-de-teste')
class FluxoExternoTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('gestor', password='senha', is_staff=True)
        self.colaborador = Colaborador.objects.create(nome='Ana', cpf=CPF_VALIDO)
        agora = timezone.now()
        self.pesquisa = Pesquisa.objects.create(
            titulo='eNPS trimestral', data_inicio=agora + timedelta(hours=1),
            data_final=agora + timedelta(days=1), criado_por=self.staff,
        )
        for ordem, tipo in enumerate(('NOTA_0_10', 'TEXTO', 'TEXTO'), 1):
            Pergunta.objects.create(pesquisa=self.pesquisa, texto_pergunta=f'Pergunta {ordem}', tipo_resposta=tipo, ordem=ordem)
        Pesquisa.objects.filter(pk=self.pesquisa.pk).update(data_inicio=agora - timedelta(minutes=1))
        self.pesquisa.refresh_from_db()
        self.client = Client()

    def test_fluxo_completo_e_bloqueio_de_duplicidade(self):
        entrada = reverse('pesquisas:responder', args=[self.pesquisa.link_uuid])
        self.assertContains(self.client.get(entrada), self.pesquisa.titulo)
        resposta = self.client.post(entrada, {'cpf': CPF_VALIDO})
        self.assertRedirects(resposta, reverse('pesquisas:responder_etapa', args=[self.pesquisa.link_uuid, 1]))
        for etapa, valor in ((1, 10), (2, 'Muito bom'), (3, 'Continuem')):
            resposta = self.client.post(reverse('pesquisas:responder_etapa', args=[self.pesquisa.link_uuid, etapa]), {'valor': valor})
        self.assertRedirects(resposta, reverse('pesquisas:agradecimento', args=[self.pesquisa.link_uuid]))
        self.assertContains(self.client.get(resposta.url), 'Obrigado por participar')
        registro = RespostaPesquisa.objects.get()
        self.assertEqual(registro.hash_cpf_respondente, gerar_hash_cpf(CPF_VALIDO))
        self.assertEqual(registro.detalhes.count(), 3)
        self.assertFalse(RespostaPesquisa.objects.filter(hash_cpf_respondente=CPF_VALIDO).exists())
        resposta = self.client.post(entrada, {'cpf': CPF_VALIDO})
        self.assertContains(resposta, 'já foi enviada')

    def test_usuario_nao_staff_nao_acessa_dashboard(self):
        comum = User.objects.create_user('comum', password='senha')
        self.client.force_login(comum)
        resposta = self.client.get(reverse('pesquisas:dashboard'))
        self.assertEqual(resposta.status_code, 302)

    def test_staff_renderiza_dashboard_e_relatorio(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('pesquisas:dashboard')), 'Dashboard')
        self.assertContains(self.client.get(reverse('pesquisas:resultados', args=[self.pesquisa.pk])), 'Resultados consolidados')
