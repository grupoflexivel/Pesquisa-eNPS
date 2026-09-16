from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from pesquisas.forms import BootstrapMixin
from pesquisas.models import somente_digitos, validar_documento

from .models import FormularioDesligamento, OpcaoPergunta, PerguntaDesligamento


class FormularioDesligamentoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = FormularioDesligamento
        fields = ('nome', 'iniciativa')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_bootstrap()


class PerguntaDesligamentoForm(BootstrapMixin, forms.ModelForm):
    opcoes_texto = forms.CharField(
        label='Opções de resposta (uma por linha)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Digite uma opção por linha'}),
    )

    class Meta:
        model = PerguntaDesligamento
        fields = ('texto_pergunta', 'tipo_resposta', 'ordem')
        widgets = {'texto_pergunta': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['opcoes_texto'].initial = '\n'.join(
                self.instance.opcoes.values_list('texto_opcao', flat=True)
            )
        self.aplicar_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo_resposta')
        opcoes = [linha.strip() for linha in (cleaned_data.get('opcoes_texto') or '').splitlines() if linha.strip()]
        if tipo in PerguntaDesligamento.OPCOES_TIPOS and len(opcoes) < 2:
            self.add_error('opcoes_texto', 'Informe ao menos duas opções de resposta.')
        cleaned_data['opcoes'] = opcoes
        return cleaned_data

    def save(self, commit=True):
        pergunta = super().save(commit=commit)
        if commit:
            self._salvar_opcoes(pergunta)
        return pergunta

    def _salvar_opcoes(self, pergunta):
        pergunta.opcoes.all().delete()
        if pergunta.tipo_resposta in PerguntaDesligamento.OPCOES_TIPOS:
            OpcaoPergunta.objects.bulk_create([
                OpcaoPergunta(pergunta=pergunta, texto_opcao=texto, ordem=indice)
                for indice, texto in enumerate(self.cleaned_data.get('opcoes') or [], start=1)
            ])


class BasePerguntaDesligamentoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        validas = [form for form in self.forms if form.cleaned_data and not form.cleaned_data.get('DELETE', False)]
        if len(validas) < 1:
            raise forms.ValidationError('Cadastre ao menos uma pergunta.')
        ordens = [form.cleaned_data['ordem'] for form in validas]
        if len(ordens) != len(set(ordens)):
            raise forms.ValidationError('A ordem das perguntas não pode se repetir.')


PerguntaDesligamentoFormSet = inlineformset_factory(
    FormularioDesligamento, PerguntaDesligamento, form=PerguntaDesligamentoForm, formset=BasePerguntaDesligamentoFormSet,
    extra=1, min_num=1, validate_min=True, can_delete=True,
)


class ValidarDocumentoDesligamentoForm(BootstrapMixin, forms.Form):
    documento = forms.CharField(
        label='CPF ou CNPJ', max_length=18,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off', 'maxlength': '18'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aplicar_bootstrap()

    def clean_documento(self):
        documento = somente_digitos(self.cleaned_data['documento'])
        validar_documento(documento)
        return documento


class ResponderPerguntaDesligamentoForm(BootstrapMixin, forms.Form):
    def __init__(self, pergunta, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pergunta = pergunta
        tipo = pergunta.tipo_resposta
        if tipo == PerguntaDesligamento.TipoResposta.TEXTO:
            self.fields['valor'] = forms.CharField(
                label='Sua resposta', widget=forms.Textarea(attrs={'rows': 5}), max_length=5000,
            )
        elif tipo == PerguntaDesligamento.TipoResposta.NOTA_0_10:
            self.fields['valor'] = forms.TypedChoiceField(
                label='Sua nota', choices=[(i, str(i)) for i in range(11)], coerce=int, widget=forms.RadioSelect,
            )
        elif tipo == PerguntaDesligamento.TipoResposta.RADIO:
            opcoes = [(opcao.pk, opcao.texto_opcao) for opcao in pergunta.opcoes.all()]
            self.fields['valor'] = forms.TypedChoiceField(
                label='Selecione uma opção', choices=opcoes, coerce=int, widget=forms.RadioSelect,
            )
        else:
            opcoes = [(opcao.pk, opcao.texto_opcao) for opcao in pergunta.opcoes.all()]
            self.fields['valor'] = forms.TypedMultipleChoiceField(
                label='Selecione uma ou mais opções', choices=opcoes, coerce=int, widget=forms.CheckboxSelectMultiple,
            )
        self.aplicar_bootstrap()
