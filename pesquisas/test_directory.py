import uuid
from unittest.mock import patch

from django.test import TestCase, override_settings

from .directory import DirectoryClient, DirectoryResult


class FakeLdap3Connection:
    """Reproduz a assinatura real do ldap3: open() devolve None em sucesso
    (nao um booleano) e bind()/start_tls() devolvem bool."""

    instances = []

    def __init__(self, server, user=None, password=None, **kwargs):
        self.user = user
        self.password = password
        self.response = []
        self.result = {}
        FakeLdap3Connection.instances.append(self)

    def open(self):
        return None

    def start_tls(self):
        return True

    def bind(self):
        return self.password in {'SenhaCorretaAD!2026', 'SenhaServico!2026'}

    def search(self, *args, **kwargs):
        self.response = [{
            'type': 'searchResEntry',
            'dn': 'CN=Joao Silva,OU=Users,DC=empresa,DC=local',
            'raw_attributes': {'objectGUID': [uuid.uuid4().bytes]},
        }]

    def unbind(self):
        pass


@override_settings(
    LDAP_SERVER='dc01.empresa.local:389',
    LDAP_DOMAIN='empresa.local',
    LDAP_BASE_DN='DC=empresa,DC=local',
    LDAP_BIND_USER='svc-enps',
    LDAP_BIND_PASSWORD='SenhaServico!2026',
)
class DirectoryClientConnectionTests(TestCase):
    """Regressao: connection.open() do ldap3 nao e booleano.

    Antes da correcao, `_open_secure_connection` tratava o retorno None
    de connection.open() (sucesso) como falha, e todo login de AD virava
    DirectoryResult.UNAVAILABLE mesmo com credenciais corretas.
    """

    def setUp(self):
        FakeLdap3Connection.instances = []

    @patch('ldap3.Connection', FakeLdap3Connection)
    def test_find_user_nao_reporta_indisponivel_quando_open_tem_sucesso(self):
        client = DirectoryClient()
        result = client.find_user('joao.silva')

        self.assertNotEqual(result, DirectoryResult.UNAVAILABLE)
        self.assertEqual(result.dn, 'CN=Joao Silva,OU=Users,DC=empresa,DC=local')

    @patch('ldap3.Connection', FakeLdap3Connection)
    def test_verify_credentials_aceita_senha_correta(self):
        client = DirectoryClient()
        result = client.verify_credentials('CN=Joao Silva,OU=Users,DC=empresa,DC=local', 'SenhaCorretaAD!2026')

        self.assertEqual(result, DirectoryResult.OK)
