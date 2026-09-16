from django.contrib import admin

from .models import (
    DetalheRespostaDesligamento, Desligamento, FormularioDesligamento, OpcaoPergunta, PerguntaDesligamento,
    RespostaDesligamento,
)


class OpcaoPerguntaInline(admin.TabularInline):
    model = OpcaoPergunta
    extra = 2


class PerguntaDesligamentoInline(admin.TabularInline):
    model = PerguntaDesligamento
    extra = 1
    min_num = 1
    validate_min = True


@admin.register(FormularioDesligamento)
class FormularioDesligamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'iniciativa', 'criado_por', 'data_criacao')
    list_filter = ('iniciativa',)
    readonly_fields = ('link_uuid', 'criado_por')
    inlines = (PerguntaDesligamentoInline,)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(PerguntaDesligamento)
class PerguntaDesligamentoAdmin(admin.ModelAdmin):
    list_display = ('formulario', 'ordem', 'texto_pergunta', 'tipo_resposta')
    list_filter = ('formulario', 'tipo_resposta')
    inlines = (OpcaoPerguntaInline,)


@admin.register(Desligamento)
class DesligamentoAdmin(admin.ModelAdmin):
    list_display = ('colaborador', 'iniciativa', 'status', 'formulario', 'data_criacao', 'data_resposta')
    list_filter = ('status', 'iniciativa')
    search_fields = ('colaborador__nome', 'colaborador__documento')
    readonly_fields = ('criado_por', 'data_criacao')


@admin.register(RespostaDesligamento)
class RespostaDesligamentoAdmin(admin.ModelAdmin):
    list_display = ('id', 'desligamento', 'data_resposta')
    readonly_fields = ('desligamento', 'data_resposta', 'hash_documento_respondente')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DetalheRespostaDesligamento)
class DetalheRespostaDesligamentoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pergunta', 'resposta')
    readonly_fields = ('resposta', 'pergunta', 'valor_texto', 'valor_inteiro', 'opcoes')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
