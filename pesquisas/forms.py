from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from .models import Colaborador, Pergunta, Pesquisa, somente_digitos, validar_documento


class BootstrapMixin:
    def aplicar_bootstrap(self):
        for field in self.fields.values():
            css = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            if isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            field.widget.attrs['class'] = css


class ColaboradorForm(BootstrapMixin, forms.ModelForm):
    documento = forms.CharField(
        label='CPF ou CNPJ', max_length=18,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': '18', 'placeholder': 'Digite CPF ou CNPJ'}),
    )
    
    is_superuser = forms.BooleanField(
        label='Tornar superusuário', 
        required=False,
        help_text='Indica que este colaborador tem acesso total ao sistema administrativo.'
    )
    
    username = forms.CharField(
        label='Nome de usuário (Login)',
        max_length=150,
        required=False,
        help_text='Informe o login que este usuário usará no sistema.'
    )

    class Meta:
        model = Colaborador
        fields = ('nome', 'documento', 'empresa', 'ativo', 'is_superuser', 'username')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk and self.instance.usuario_id:
            self.fields['is_superuser'].initial = self.instance.usuario.is_superuser
            self.fields['username'].initial = self.instance.usuario.username
            
        self.aplicar_bootstrap()

    def clean_documento(self):
        documento = somente_digitos(self.cleaned_data['documento'])
        validar_documento(documento)
        return documento

    def clean(self):
        cleaned_data = super().clean()
        is_superuser = cleaned_data.get('is_superuser')
        username = (cleaned_data.get('username') or '').strip().lower()
        cleaned_data['username'] = username

        # Validação: se marcou para ser superusuário, o username se torna obrigatório
        if is_superuser and not username:
            self.add_error('username', 'Informe o nome de usuário (login) para criar o superusuário.')
            
        # Validar se o username já existe no sistema caso esteja criando um novo
        if username:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_qs = User.objects.filter(username__iexact=username)
            if self.instance and self.instance.pk and self.instance.usuario_id:
                user_qs = user_qs.exclude(pk=self.instance.usuario_id)
            if user_qs.exists():
                self.add_error('username', 'Este nome de usuário já está em uso.')

        return cleaned_data

    def save(self, commit=True):
        colaborador = super().save(commit=False)
        tornar_super = self.cleaned_data.get('is_superuser', False)
        username = self.cleaned_data.get('username')

        if commit:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            if tornar_super and username:
                if colaborador.usuario:
                    user = colaborador.usuario
                    source_before = user.auth_source
                    user.username = username
                    user.is_staff = True
                    user.is_superuser = True
                    user.first_name = colaborador.nome
                else:
                    user, _ = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'is_staff': True,
                            'is_superuser': True,
                            'first_name': colaborador.nome
                        }
                    )
                    source_before = user.auth_source
                    user.is_staff = True
                    user.is_superuser = True

                # O login informado neste cadastro é o sAMAccountName do AD.
                # Nunca validar esse usuário por senha local.
                user.auth_source = User.AuthSource.DIRECTORY
                if source_before != User.AuthSource.DIRECTORY:
                    user.directory_guid = None
                if user.has_usable_password():
                    user.set_unusable_password()
                user.save()
                colaborador.usuario = user
            else:
                if colaborador.usuario:
                    colaborador.usuario.is_superuser = False
                    colaborador.usuario.is_staff = False
                    colaborador.usuario.save()
                    colaborador.usuario = None # Desvincula se desmarcar

            colaborador.save()
            self.save_m2m()

        return colaborador


class PesquisaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Pesquisa
        fields = ('titulo', 'data_inicio', 'data_final')
        widgets = {
            'data_inicio': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
            'data_final': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_inicio'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.fields['data_final'].input_formats = ('%Y-%m-%dT%H:%M',)
        self.aplicar_bootstrap()

    def clean_data_inicio(self):
        data_inicio = self.cleaned_data['data_inicio']
        if not self.instance.pk and data_inicio <= timezone.now():
            raise forms.ValidationError('A data inicial de uma nova pesquisa deve estar no futuro.')
        return data_inicio


class PerguntaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Pergunta
        fields = ('texto_pergunta', 'tipo_resposta', 'ordem')
        widgets = {'texto_pergunta': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_bootstrap()


class BasePerguntaFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        validas = [form for form in self.forms if form.cleaned_data and not form.cleaned_data.get('DELETE', False)]
        if len(validas) < 3:
            raise forms.ValidationError('Cadastre no mínimo 3 perguntas.')
        ordens = [form.cleaned_data['ordem'] for form in validas]
        if len(ordens) != len(set(ordens)):
            raise forms.ValidationError('A ordem das perguntas não pode se repetir.')


PerguntaFormSet = inlineformset_factory(
    Pesquisa, Pergunta, form=PerguntaForm, formset=BasePerguntaFormSet,
    extra=3, min_num=3, validate_min=True, can_delete=True,
)


class ValidarCPFForm(BootstrapMixin, forms.Form):
    documento = forms.CharField(
        label='CPF ou CNPJ', max_length=18, 
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off', 'maxlength': '18'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_bootstrap()

    def clean_documento(self):
        documento = somente_digitos(self.cleaned_data['documento'])
        validar_documento(documento)
        return documento


class ResponderPerguntaForm(BootstrapMixin, forms.Form):
    def __init__(self, pergunta, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pergunta = pergunta
        if pergunta.tipo_resposta == Pergunta.TipoResposta.TEXTO:
            self.fields['valor'] = forms.CharField(label='Sua resposta', widget=forms.Textarea(attrs={'rows': 5}), max_length=5000)
        else:
            self.fields['valor'] = forms.TypedChoiceField(
                label='Sua nota', choices=[(i, str(i)) for i in range(11)], coerce=int, widget=forms.RadioSelect
            )
        self.aplicar_bootstrap()