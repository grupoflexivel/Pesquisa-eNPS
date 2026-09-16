from django.urls import path

from . import views


app_name = 'desligamentos'

urlpatterns = [
    path('desligamentos/', views.kanban, name='kanban'),
    path('desligamentos/formularios/', views.formulario_lista, name='formulario_lista'),
    path('desligamentos/formularios/novo/', views.formulario_criar, name='formulario_criar'),
    path('desligamentos/formularios/<int:pk>/editar/', views.formulario_editar, name='formulario_editar'),
    path('desligamentos/formularios/<int:pk>/excluir/', views.formulario_excluir, name='formulario_excluir'),
    path('desligamentos/<int:pk>/enviar/', views.desligamento_marcar_enviado, name='desligamento_marcar_enviado'),
    path('desligamentos/<int:pk>/respostas/', views.desligamento_respostas, name='desligamento_respostas'),
    path('desligamento/<uuid:link_uuid>/', views.validar_participante, name='responder'),
    path('desligamento/<uuid:link_uuid>/pergunta/<int:etapa>/', views.responder_etapa, name='responder_etapa'),
    path('desligamento/<uuid:link_uuid>/obrigado/', views.agradecimento, name='agradecimento'),
]
