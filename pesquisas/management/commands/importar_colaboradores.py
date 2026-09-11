import csv
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pesquisas.models import Colaborador, Empresa, somente_digitos


class Command(BaseCommand):
    help = 'Importa colaboradores ativos de um CSV UTF-8 com as colunas nome, documento e empresa (aceita vírgula ou ponto e vírgula).'

    def add_arguments(self, parser):
        parser.add_argument('arquivo_csv', type=Path)

    def handle(self, *args, **options):
        caminho = options['arquivo_csv'].resolve()
        if not caminho.is_file():
            raise CommandError(f'Arquivo não encontrado: {caminho}')

        criados = atualizados = 0
        try:
            with caminho.open('r', encoding='utf-8-sig', newline='') as arquivo, transaction.atomic():
                amostra = arquivo.read(2048)
                arquivo.seek(0)
                try:
                    delimitador = csv.Sniffer().sniff(amostra).delimiter
                except csv.Error:
                    delimitador = ','

                leitor = csv.DictReader(arquivo, delimiter=delimitador)
                if leitor.fieldnames != ['nome', 'documento', 'empresa']:
                    raise CommandError(
                        'O CSV deve conter exatamente as colunas nome,documento,empresa, '
                        f'nesta ordem (encontrado: {leitor.fieldnames}).'
                    )

                for numero, linha in enumerate(leitor, start=2):
                    nome = (linha.get('nome') or '').strip()
                    documento = somente_digitos(linha.get('documento'))
                    nome_empresa = ' '.join((linha.get('empresa') or '').split())
                    if not nome:
                        raise CommandError(f'Linha {numero}: nome vazio.')
                    if not nome_empresa:
                        raise CommandError(f'Linha {numero}: empresa vazia.')
                    try:
                        empresa = Empresa.objects.filter(nome__iexact=nome_empresa).first()
                        if empresa is None:
                            empresa = Empresa(nome=nome_empresa)
                            empresa.full_clean()
                            empresa.save()
                        colaborador, criado = Colaborador.objects.update_or_create(
                            documento=documento, defaults={'nome': nome, 'empresa': empresa, 'ativo': True}
                        )
                    except ValidationError as exc:
                        raise CommandError(f'Linha {numero}: {exc}') from exc
                    criados += int(criado)
                    atualizados += int(not criado)
        except (OSError, UnicodeError, csv.Error) as exc:
            raise CommandError(f'Não foi possível ler o CSV: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(f'Importação concluída: {criados} criados e {atualizados} atualizados.'))
