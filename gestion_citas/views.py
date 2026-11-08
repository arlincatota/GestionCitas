from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AtencionClinicaForm,
    CitaAgendaForm,
    MedicoEdicionForm,
    MedicoRegistroForm,
    PacienteEdicionForm,
    PacienteRegistroForm,
)
from .models import Atencion, Cita, Medico, Paciente


def _es_administrativo(user):
    return user.is_staff or user.is_superuser or user.groups.filter(
        name__in=("Administrativo", "Administrativos")
    ).exists()


def _rol_requerido(verificar_rol):
    def decorador(vista):
        @wraps(vista)
        @login_required
        def protegida(request, *args, **kwargs):
            if not verificar_rol(request.user):
                return HttpResponseForbidden(
                    "No tienes permiso para acceder a esta página."
                )
            return vista(request, *args, **kwargs)

        return protegida

    return decorador


def _redireccion_por_rol(user):
    if _es_administrativo(user):
        return redirect("panel_administrativo")
    if user.groups.filter(name="Medicos").exists() or Medico.objects.filter(
        user=user
    ).exists():
        return redirect("panel_medico")
    if user.groups.filter(name="Pacientes").exists() or Paciente.objects.filter(
        user=user
    ).exists():
        return redirect("panel_paciente")
    return redirect("login")


def dashboard_router(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return _redireccion_por_rol(request.user)


def _post_action(request, *button_names):
    return request.POST.get("action") or next(
        (button for button in button_names if button in request.POST),
        "",
    )


def login_view(request):
    if request.user.is_authenticated:
        destino = _redireccion_por_rol(request.user)
        if destino:
            return destino

    formulario = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.get_user()
        destino = _redireccion_por_rol(usuario)
        if destino:
            login(request, usuario)
            return destino
        formulario.add_error(None, "La cuenta no tiene un perfil o rol asignado.")

    return render(request, "gestion_citas/login.html", {"formulario": formulario})


iniciar_sesion = login_view


@login_required
@require_POST
def cerrar_sesion(request):
    logout(request)
    messages.success(request, "Has cerrado sesión.")
    return redirect("login")


@_rol_requerido(_es_administrativo)
def panel_administrativo(request):
    paciente_form = PacienteRegistroForm()
    medico_form = MedicoRegistroForm()
    cita_form = CitaAgendaForm()

    if request.method == "POST":
        action = _post_action(
            request,
            "registrar_paciente",
            "registrar_medico",
            "agendar_cita",
            "cancelar_cita",
        )

        if action in ("registrar_paciente", "register_patient"):
            paciente_form = PacienteRegistroForm(request.POST)
            if paciente_form.is_valid():
                try:
                    paciente_form.save()
                except IntegrityError:
                    messages.error(
                        request,
                        "Ya existe una cuenta o paciente con esos datos.",
                    )
                else:
                    messages.success(
                        request,
                        "Paciente registrado correctamente.",
                    )
                    paciente_form = PacienteRegistroForm()

        elif action in ("registrar_medico", "register_doctor"):
            medico_form = MedicoRegistroForm(request.POST)
            if medico_form.is_valid():
                try:
                    medico_form.save()
                except IntegrityError:
                    messages.error(
                        request,
                        "Ya existe una cuenta con ese nombre de usuario.",
                    )
                else:
                    messages.success(request, "Médico registrado correctamente.")
                    medico_form = MedicoRegistroForm()

        elif action in ("agendar_cita", "schedule_appointment"):
            cita_form = CitaAgendaForm(request.POST)
            if cita_form.is_valid():
                datos = cita_form.cleaned_data
                cita_confirmada_en_horario = Cita.objects.filter(
                    fecha=datos["fecha"],
                    hora=datos["hora"],
                    estado=Cita.Estado.CONFIRMADA,
                )
                if cita_confirmada_en_horario.filter(
                    id_paciente=datos["id_paciente"],
                ).exists():
                    messages.error(
                        request,
                        "Error: El paciente ya tiene otra cita programada en esa fecha y hora exacta.",
                    )
                elif cita_confirmada_en_horario.filter(
                    id_medico=datos["id_medico"],
                ).exists():
                    messages.error(
                        request,
                        "Error: El médico seleccionado ya tiene una cita ocupada en ese horario.",
                    )
                else:
                    try:
                        with transaction.atomic():
                            cita_form.save()
                    except IntegrityError:
                        messages.error(
                            request,
                            "Error: El médico seleccionado ya tiene una cita ocupada en ese horario.",
                        )
                    else:
                        messages.success(request, "Cita agendada correctamente.")
                        cita_form = CitaAgendaForm()

        elif action in ("cancelar_cita", "cancel_appointment"):
            cita_id = request.POST.get("cita_id", "")
            if not cita_id.isdigit():
                messages.error(request, "La cita seleccionada no es válida.")
            else:
                cita = get_object_or_404(Cita, pk=cita_id)
                if cita.estado != Cita.Estado.CONFIRMADA:
                    messages.error(
                        request,
                        "Solo se pueden cancelar citas confirmadas.",
                    )
                else:
                    cita.estado = Cita.Estado.CANCELADA
                    cita.save(update_fields=["estado"])
                    messages.success(request, "Cita cancelada correctamente.")
        else:
            messages.error(request, "No se reconoció la acción solicitada.")

    hoy = timezone.localdate()
    return render(
        request,
        "gestion_citas/panel_administrativo.html",
        {
            "pacientes": Paciente.objects.select_related("user").all(),
            "medicos": Medico.objects.select_related("user").all(),
            "citas": Cita.objects.select_related(
                "id_paciente__user",
                "id_medico__user",
            ).all(),
            "paciente_form": paciente_form,
            "medico_form": medico_form,
            "cita_form": cita_form,
            "total_doctores": Medico.objects.count(),
            "total_pacientes": Paciente.objects.count(),
            "citas_hoy": Cita.objects.filter(fecha=hoy).count(),
        },
    )


@_rol_requerido(_es_administrativo)
def editar_paciente(request, paciente_id):
    paciente = get_object_or_404(
        Paciente.objects.select_related("user"),
        pk=paciente_id,
    )
    formulario = PacienteEdicionForm(
        request.POST or None,
        instance=paciente,
    )
    if request.method == "POST":
        if formulario.is_valid():
            try:
                formulario.save()
            except IntegrityError:
                messages.error(
                    request,
                    "No se pudo actualizar el paciente; verifica que sus datos no estén duplicados.",
                )
            else:
                messages.success(request, "Paciente actualizado correctamente.")
                return redirect("panel_administrativo")
        else:
            messages.error(request, "Revisa los datos del paciente.")

    return render(
        request,
        "gestion_citas/editar_paciente.html",
        {"paciente": paciente, "formulario": formulario},
    )


@_rol_requerido(_es_administrativo)
def editar_medico(request, medico_id):
    medico = get_object_or_404(
        Medico.objects.select_related("user"),
        pk=medico_id,
    )
    formulario = MedicoEdicionForm(request.POST or None, instance=medico)
    if request.method == "POST":
        if formulario.is_valid():
            try:
                formulario.save()
            except IntegrityError:
                messages.error(
                    request,
                    "No se pudo actualizar el médico; verifica que sus datos no estén duplicados.",
                )
            else:
                messages.success(request, "Médico actualizado correctamente.")
                return redirect("panel_administrativo")
        else:
            messages.error(request, "Revisa los datos del médico.")

    return render(
        request,
        "gestion_citas/editar_medico.html",
        {"medico": medico, "formulario": formulario},
    )


@_rol_requerido(_es_administrativo)
@require_POST
def eliminar_paciente(request, paciente_id):
    paciente = get_object_or_404(
        Paciente.objects.select_related("user"),
        pk=paciente_id,
    )
    usuario = paciente.user
    with transaction.atomic():
        paciente.delete()
        usuario.delete()
    messages.success(request, "Paciente y su cuenta fueron eliminados correctamente.")
    return redirect("panel_administrativo")


@_rol_requerido(_es_administrativo)
@require_POST
def eliminar_medico(request, medico_id):
    medico = get_object_or_404(
        Medico.objects.select_related("user"),
        pk=medico_id,
    )
    usuario = medico.user
    with transaction.atomic():
        medico.delete()
        usuario.delete()
    messages.success(request, "Médico y su cuenta fueron eliminados correctamente.")
    return redirect("panel_administrativo")


@_rol_requerido(lambda user: Medico.objects.filter(user=user).exists())
def panel_medico(request):
    medico = get_object_or_404(Medico, user=request.user)
    paciente_form = PacienteRegistroForm()
    bound_atencion_form = None
    selected_patient_id = request.GET.get("paciente_id", "")
    selected_appointment_id = request.GET.get("cita_id", "")

    if request.method == "POST":
        action = _post_action(
            request,
            "registrar_paciente",
            "registrar_atencion",
        )

        if action in ("registrar_paciente", "register_patient"):
            paciente_form = PacienteRegistroForm(request.POST)
            if paciente_form.is_valid():
                try:
                    paciente_form.save()
                except IntegrityError:
                    messages.error(
                        request,
                        "Ya existe una cuenta o paciente con esos datos.",
                    )
                else:
                    messages.success(request, "Paciente registrado correctamente.")
                    paciente_form = PacienteRegistroForm()

        elif action in ("registrar_atencion", "register_attention"):
            cita_id = request.POST.get("cita_id", "")
            selected_patient_id = request.POST.get("paciente_id", "")
            selected_appointment_id = cita_id
            if not cita_id.isdigit():
                messages.error(request, "La cita seleccionada no es válida.")
            else:
                cita = get_object_or_404(
                    Cita,
                    pk=cita_id,
                    id_medico=medico,
                    estado=Cita.Estado.CONFIRMADA,
                )
                bound_atencion_form = AtencionClinicaForm(
                    request.POST,
                    prefix=f"cita-{cita_id}",
                )
                if bound_atencion_form.is_valid():
                    if _guardar_atencion(request, cita, bound_atencion_form):
                        query = (
                            f"?paciente_id={cita.id_paciente_id}"
                            f"&cita_id={cita.pk}"
                        )
                        return redirect(f"{reverse('panel_medico')}{query}")

        else:
            messages.error(request, "No se reconoció la acción solicitada.")

    hoy = timezone.localdate()
    citas_hoy = (
        Cita.objects.filter(
            id_medico=medico,
            fecha=hoy,
            estado__in=(Cita.Estado.CONFIRMADA, Cita.Estado.ATENDIDA),
        )
        .select_related("id_paciente__user")
        .order_by("hora")
    )

    paciente_historia = None
    historial_medico = Atencion.objects.none()
    cita_seleccionada = None
    atencion_form = None
    if selected_patient_id:
        if selected_patient_id.isdigit():
            paciente_historia = get_object_or_404(
                Paciente.objects.select_related("user"),
                pk=selected_patient_id,
            )
            if not Cita.objects.filter(
                id_paciente=paciente_historia,
                id_medico=medico,
            ).exists():
                return HttpResponseForbidden(
                    "No tienes autorización para consultar el historial de este paciente."
                )
            historial_medico = (
                Atencion.objects.filter(id_cita__id_paciente=paciente_historia)
                .select_related(
                    "id_cita",
                    "id_cita__id_medico__user",
                )
                .order_by("-fecha_registro")
            )
            if selected_appointment_id:
                if not selected_appointment_id.isdigit():
                    messages.error(request, "La cita seleccionada no es válida.")
                else:
                    cita_seleccionada = Cita.objects.filter(
                        pk=selected_appointment_id,
                        id_paciente=paciente_historia,
                        id_medico=medico,
                        fecha=hoy,
                    ).first()
                    if cita_seleccionada is None:
                        messages.error(
                            request,
                            "La cita seleccionada no pertenece a la agenda de hoy.",
                        )
            else:
                cita_seleccionada = citas_hoy.filter(
                    id_paciente=paciente_historia,
                    estado=Cita.Estado.CONFIRMADA,
                ).first()

            if cita_seleccionada and cita_seleccionada.estado == Cita.Estado.CONFIRMADA:
                atencion_form = (
                    bound_atencion_form
                    if bound_atencion_form is not None
                    else AtencionClinicaForm(
                        prefix=f"cita-{cita_seleccionada.pk}"
                    )
                )
        else:
            messages.error(request, "El paciente seleccionado no es válido.")

    return render(
        request,
        "gestion_citas/panel_medico.html",
        {
            "medico": medico,
            "citas": citas_hoy,
            "citas_pendientes": citas_hoy.filter(
                estado=Cita.Estado.CONFIRMADA
            ).count(),
            "citas_atendidas": citas_hoy.filter(
                estado=Cita.Estado.ATENDIDA
            ).count(),
            "paciente_form": paciente_form,
            "paciente_historia": paciente_historia,
            "historial_medico": historial_medico,
            "cita_seleccionada": cita_seleccionada,
            "atencion_form": atencion_form,
        },
    )


@_rol_requerido(lambda user: Medico.objects.filter(user=user).exists())
@require_POST
def registrar_atencion(request, cita_id):
    medico = get_object_or_404(Medico, user=request.user)
    cita = get_object_or_404(
        Cita,
        pk=cita_id,
        id_medico=medico,
        estado=Cita.Estado.CONFIRMADA,
    )
    atencion_form = AtencionClinicaForm(request.POST)
    if atencion_form.is_valid():
        _guardar_atencion(request, cita, atencion_form)
    else:
        messages.error(request, "Revisa los datos de la atención.")
    return redirect("panel_medico")


def _guardar_atencion(request, cita, atencion_form):
    try:
        with transaction.atomic():
            atencion = atencion_form.save(commit=False)
            atencion.id_cita = cita
            atencion.save()
            cita.estado = Cita.Estado.ATENDIDA
            cita.save(update_fields=["estado"])
    except IntegrityError:
        messages.error(
            request,
            "No se pudo guardar la atención; esta cita podría tener una atención registrada.",
        )
        return False
    messages.success(request, "Atención médica registrada con éxito.")
    return True


@_rol_requerido(lambda user: Paciente.objects.filter(user=user).exists())
def panel_paciente(request):
    paciente = get_object_or_404(Paciente, user=request.user)
    citas = (
        Cita.objects.filter(id_paciente=paciente)
        .select_related("id_medico__user")
        .order_by("-fecha", "hora")
    )
    return render(
        request,
        "gestion_citas/panel_paciente.html",
        {"paciente": paciente, "citas": citas},
    )
