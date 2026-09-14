from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django import forms
import logging

from .models import Colaborador, DetalheResposta, Empresa, Pergunta, Pesquisa, RespostaPesquisa, User


logger = logging.getLogger('pesquisas.auth')


class AdminUserCreationForm(UserCreationForm):
    auth_source = forms.ChoiceField(choices=User.AuthSource.choices, label='Origem da autenticação')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'auth_source')

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data['auth_source'] == User.AuthSource.DIRECTORY:
            user.set_unusable_password()
        if commit:
            user.save()
        return user


class AdminUserChangeForm(UserChangeForm):
    auth_source = forms.ChoiceField(choices=User.AuthSource.choices, label='Origem da autenticação')
    local_password = forms.CharField(
        label='Nova senha local', required=False, strip=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Obrigatória ao trocar de Active Directory para senha local.',
    )

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['auth_source'].initial = self.instance.auth_source

    def clean(self):
        cleaned = super().clean()
        if (
            self.instance.auth_source == User.AuthSource.DIRECTORY
            and cleaned.get('auth_source') == User.AuthSource.LOCAL
            and not cleaned.get('local_password')
        ):
            self.add_error('local_password', 'Defina uma nova senha local ao desvincular do AD.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        source_before = self.instance.auth_source
        source_after = self.cleaned_data['auth_source']
        user.auth_source = source_after

        if source_after == User.AuthSource.DIRECTORY:
            if source_before != User.AuthSource.DIRECTORY:
                user.set_unusable_password()
        elif source_before == User.AuthSource.DIRECTORY:
            user.directory_guid = None
            user.set_password(self.cleaned_data['local_password'])
        elif self.cleaned_data.get('local_password'):
            user.set_password(self.cleaned_data['local_password'])

        if commit:
            user.save()
        return user


admin.site.site_header = 'Administração eNPS'
admin.site.site_title = 'eNPS'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = AdminUserCreationForm
    form = AdminUserChangeForm
    list_display = ('username', 'auth_source', 'directory_guid', 'is_staff', 'is_active')
    list_filter = ('auth_source', 'is_staff', 'is_active')
    readonly_fields = ('directory_guid',)
    fieldsets = UserAdmin.fieldsets + (
        ('Autenticação corporativa', {'fields': ('auth_source', 'directory_guid', 'local_password')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Autenticação corporativa', {'fields': ('auth_source',)}),
    )
    actions = ('relink_directory_identity',)

    def save_model(self, request, obj, form, change):
        previous_source = None
        if change:
            previous_source = User.objects.only('auth_source').get(pk=obj.pk).auth_source
        super().save_model(request, obj, form, change)
        if previous_source != obj.auth_source:
            logger.info(
                'admin=%s auth_source_changed user=%s from=%s to=%s',
                request.user.username, obj.username, previous_source or '-', obj.auth_source,
            )

    @admin.action(description='Religar identidade AD (limpar objectGUID)')
    def relink_directory_identity(self, request, queryset):
        users = queryset.filter(auth_source=User.AuthSource.DIRECTORY)
        count = users.update(directory_guid=None)
        logger.info('admin=%s relink_directory_identity count=%s', request.user.username, count)
        self.message_user(request, f'{count} identidade(s) AD liberada(s) para novo vínculo.')


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'documento', 'empresa', 'ativo')
    list_filter = ('empresa', 'ativo')
    search_fields = ('nome', 'documento', 'empresa__nome')


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    search_fields = ('nome',)


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
    readonly_fields = ('pesquisa', 'data_resposta', 'hash_documento_respondente')
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
