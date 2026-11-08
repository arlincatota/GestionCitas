from django.urls import path

from . import views


urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.cerrar_sesion, name="logout"),
    path("", views.dashboard_router, name="inicio"),
    path(
        "administrativo/",
        views.panel_administrativo,
        name="panel_administrativo",
    ),
    path(
        "editar-paciente/<int:paciente_id>/",
        views.editar_paciente,
        name="editar_paciente",
    ),
    path(
        "editar-medico/<int:medico_id>/",
        views.editar_medico,
        name="editar_medico",
    ),
    path(
        "eliminar-paciente/<int:paciente_id>/",
        views.eliminar_paciente,
        name="eliminar_paciente",
    ),
    path(
        "eliminar-medico/<int:medico_id>/",
        views.eliminar_medico,
        name="eliminar_medico",
    ),
    path(
        "medico/",
        views.panel_medico,
        name="panel_medico",
    ),
    path("paciente/", views.panel_paciente, name="panel_paciente"),
    path(
        "cita/<int:cita_id>/atencion/",
        views.registrar_atencion,
        name="registrar_atencion",
    ),
]
