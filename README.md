# Sistema de pesquisas eNPS

Aplicação Django com PostgreSQL para cadastro de colaboradores, pesquisas com formulário dinâmico, resposta externa por CPF e relatórios eNPS. O CPF é usado apenas durante a validação; a participação é persistida como HMAC-SHA-256 e existe uma restrição única no banco para impedir respostas duplicadas.

## Preparação

1. Ative a venv e instale as dependências: `pip install -r requirements.txt`.
2. Crie o banco e o usuário no PostgreSQL.
3. Preencha `.env`. Em produção, troque `SECRET_KEY` e `SECRET_SALT` por segredos longos e independentes, defina `DEBUG=False` e informe `ALLOWED_HOSTS`.
4. Não altere `SECRET_SALT` após receber respostas: a troca muda os hashes e invalida a detecção de duplicidade.
5. Execute `python manage.py migrate` e `python manage.py createsuperuser`.
6. Inicie localmente com `python manage.py runserver`.

O carregamento em `enps/settings.py` usa `config(...)` da biblioteca `python-decouple`. O banco padrão é sempre PostgreSQL; SQLite é usado apenas no arquivo isolado de configuração de testes.

## CSV

O arquivo deve ser UTF-8 e conter exatamente:

```csv
nome,cpf,empresa
Ana Silva,52998224725,Filial São Paulo
```

Importe com `python manage.py importar_colaboradores Colaboradores.csv`. Empresas são criadas automaticamente, sem duplicidade de nomes (inclusive com diferenças apenas entre maiúsculas e minúsculas). Registros existentes são atualizados, vinculados à empresa informada e reativados; qualquer linha inválida cancela toda a importação.

## Regras relevantes

- Somente usuários autenticados com `is_staff=True` acessam o painel de gestão. O `/admin/` é apresentado na interface apenas a superusuários.
- Uma nova pesquisa exige pelo menos três perguntas e data inicial futura. A partir do início, o modelo, as views e o admin bloqueiam alterações.
- O relatório usa a primeira pergunta `NOTA_0_10`, ordenada por `ordem`, como pergunta eNPS.
- Como o cadastro solicitado possui apenas o estado atual `ativo`, o KPI de colaboradores ativos reflete o cadastro no momento da consulta do relatório.

## Testes

Execute `python manage.py test --settings=enps.settings_test`.
