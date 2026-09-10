from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Colaborador, DetalheResposta, Pergunta, Pesquisa, RespostaPesquisa, User


admin.site.site_header = 'Administração eNPS'
admin.site.site_title = 'eNPS'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    pass


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'cpf')


class PerguntaInline(admin.TabularInline):
    model = Pergunta
    extra = 3
    min_num = 3
    validate_min = True


@admin.register(Pesquisa)
class PesquisaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'data_inicio', 'data_final', 'edicao_bloqueada', 'criado_por')
    readonly_fields = ('link_uuid', 'criado_por')
    inlines = (PerguntaInline,)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.edicao_bloqueada:
            return tuple(field.name for field in obj._meta.fields)
        return super().get_readonly_fields(request, obj)

    def get_inline_instances(self, request, obj=None):
        if obj and obj.edicao_bloqueada:
            return []
        return super().get_inline_instances(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and obj.edicao_bloqueada:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.edicao_bloqueada:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(RespostaPesquisa)
class RespostaPesquisaAdmin(admin.ModelAdmin):
    list_display = ('id', 'pesquisa', 'data_resposta')
    list_filter = ('pesquisa',)
    readonly_fields = ('pesquisa', 'data_resposta', 'hash_cpf_respondente')
    search_fields = ('pesquisa__titulo',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DetalheResposta)
class DetalheRespostaAdmin(admin.ModelAdmin):
    list_display = ('id', 'pergunta', 'resposta_pesquisa')
    readonly_fields = ('resposta_pesquisa', 'pergunta', 'valor_texto', 'valor_inteiro')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
