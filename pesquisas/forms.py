from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from .models import Colaborador, Pergunta, Pesquisa, somente_digitos, validar_cpf


class BootstrapMixin:
    def aplicar_bootstrap(self):
        for field in self.fields.values():
            css = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            if isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            field.widget.attrs['class'] = css


class ColaboradorForm(BootstrapMixin, forms.ModelForm):
    cpf = forms.CharField(
        label='CPF', max_length=14,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': '14'}),
    )

    class Meta:
        model = Colaborador
        fields = ('nome', 'cpf', 'ativo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_bootstrap()

    def clean_cpf(self):
        cpf = somente_digitos(self.cleaned_data['cpf'])
        validar_cpf(cpf)
        return cpf


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
    cpf = forms.CharField(label='CPF', max_length=14, widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_bootstrap()

    def clean_cpf(self):
        cpf = somente_digitos(self.cleaned_data['cpf'])
        validar_cpf(cpf)
        return cpf


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
