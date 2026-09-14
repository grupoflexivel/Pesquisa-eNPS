from django.contrib.auth.views import LoginView
from django.contrib.auth.views import PasswordChangeView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy

from .authentication import AuthenticationOutcome


OUTCOME_MESSAGES = {
    AuthenticationOutcome.DIRECTORY_UNAVAILABLE: 'Serviço de autenticação indisponível. Tente em instantes.',
    AuthenticationOutcome.DISABLED: 'Conta indisponível. Procure a TI.',
    AuthenticationOutcome.EXPIRED: 'Conta indisponível. Procure a TI.',
    AuthenticationOutcome.LOCKED: 'Conta bloqueada. Procure a TI.',
    AuthenticationOutcome.PASSWORD_EXPIRED: 'Sua senha de rede expirou. Altere-a no Windows.',
    AuthenticationOutcome.MUST_CHANGE_PASSWORD: 'Sua senha de rede precisa ser alterada no Windows.',
    AuthenticationOutcome.IDENTITY_MISMATCH: 'Usuário ou senha inválidos.',
    AuthenticationOutcome.INVALID: 'Usuário ou senha inválidos.',
}


class ENPSLoginView(LoginView):
    template_name = 'registration/login.html'

    def form_invalid(self, form):
        outcome = getattr(self.request, 'auth_outcome', AuthenticationOutcome.INVALID)
        form.errors.clear()
        form.add_error(None, OUTCOME_MESSAGES.get(outcome, OUTCOME_MESSAGES[AuthenticationOutcome.INVALID]))
        return super().form_invalid(form)


class LocalPasswordChangeView(PasswordChangeView):
    template_name = 'registration/password_change_form.html'
    success_url = reverse_lazy('password_change_done')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if request.user.auth_source == request.user.AuthSource.DIRECTORY:
            messages.info(request, 'A senha de usuários do AD deve ser alterada no Windows.')
            return redirect('pesquisas:dashboard')
        return super().dispatch(request, *args, **kwargs)
