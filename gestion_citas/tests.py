from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.forms import Select
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import (
    MedicoEdicionForm,
    MedicoRegistroForm,
    PacienteEdicionForm,
    PacienteRegistroForm,
)
from .models import Atencion, Cita, Medico, Paciente


class RegistroPerfilFormTests(TestCase):
    def test_paciente_form_creates_user_group_and_profile(self):
        form = PacienteRegistroForm(
            data={
                "username": "paciente-test",
                "password": "Unica!ClaveSegura2026",
                "first_name": "Ana",
                "last_name": "Paciente",
                "cedula": "1234567890",
                "celular": "0991234567",
                "sexo": "Femenino",
                "correo": "ana@example.com",
                "fecha_nacimiento": "1990-05-12",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        paciente = form.save()
        usuario = get_user_model().objects.get(username="paciente-test")

        self.assertIsInstance(paciente, Paciente)
        self.assertEqual(paciente.user, usuario)
        self.assertEqual(paciente.sexo, "Femenino")
        self.assertEqual(paciente.correo, "ana@example.com")
        self.assertEqual(paciente.fecha_nacimiento, date(1990, 5, 12))
        self.assertEqual(paciente.user.get_full_name(), "Ana Paciente")
        self.assertTrue(usuario.check_password("Unica!ClaveSegura2026"))
        self.assertTrue(usuario.groups.filter(name="Pacientes").exists())

    def test_medico_form_creates_user_group_and_profile(self):
        form = MedicoRegistroForm(
            data={
                "username": "medico-test",
                "password": "Unica!ClaveSegura2026",
                "first_name": "Luis",
                "last_name": "Medico",
                "especialidad": "Cardiología",
                "correo": "luis@utc.edu.ec",
                "celular": "0991234567",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        medico = form.save()
        usuario = get_user_model().objects.get(username="medico-test")

        self.assertIsInstance(medico, Medico)
        self.assertEqual(medico.user, usuario)
        self.assertEqual(medico.user.get_full_name(), "Luis Medico")
        self.assertEqual(medico.correo, "luis@utc.edu.ec")
        self.assertEqual(medico.celular, "0991234567")
        self.assertTrue(usuario.check_password("Unica!ClaveSegura2026"))
        self.assertTrue(usuario.groups.filter(name="Medicos").exists())

    def test_duplicate_username_is_rejected(self):
        get_user_model().objects.create_user(
            username="usuario-duplicado",
            password="Unica!ClaveSegura2026",
        )
        form = PacienteRegistroForm(
            data={
                "username": "usuario-duplicado",
                "password": "Otra!ClaveSegura2026",
                "first_name": "Ana",
                "last_name": "Paciente",
                "cedula": "1234567890",
                "celular": "0991234567",
                "sexo": "Masculino",
                "correo": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_paciente_form_requires_exactly_ten_ascii_digits(self):
        datos = {
            "username": "paciente-validation",
            "password": "Unica!ClaveSegura2026",
            "first_name": "Ana",
            "last_name": "Paciente",
            "cedula": "1234567890",
            "celular": "0991234567",
            "sexo": "Femenino",
            "correo": "",
        }

        for field, invalid_values in (
            ("cedula", ("123456789", "12345678901", "12345abc90", "１２３４５６７８９０")),
            ("celular", ("099123456", "09912345678", "09912abc67", "０９９１２３４５６７")),
        ):
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    form_data = {**datos, field: value}
                    form = PacienteRegistroForm(data=form_data)
                    self.assertFalse(form.is_valid())
                    self.assertIn(field, form.errors)

    def test_paciente_sexo_uses_bootstrap_select(self):
        form = PacienteRegistroForm()

        self.assertIsInstance(form.fields["sexo"].widget, Select)
        self.assertEqual(form.fields["sexo"].widget.attrs["class"], "form-select")
        self.assertEqual(
            form.fields["sexo"].choices,
            [
                ("", "Seleccione..."),
                ("Masculino", "Masculino"),
                ("Femenino", "Femenino"),
            ],
        )

    def test_paciente_email_requires_valid_address_and_spanish_error(self):
        datos = {
            "username": "paciente-email-validation",
            "password": "Unica!ClaveSegura2026",
            "first_name": "Ana",
            "last_name": "Paciente",
            "cedula": "1234567890",
            "celular": "0991234567",
            "sexo": "Femenino",
        }

        for correo in ("sin-arroba.com", "ana@", "ana@.com"):
            with self.subTest(correo=correo):
                form = PacienteRegistroForm(data={**datos, "correo": correo})
                self.assertFalse(form.is_valid())
                self.assertEqual(
                    form.errors["correo"],
                    [
                        "Ingrese una dirección de correo electrónico válida "
                        "que contenga @ y un dominio."
                    ],
                )

        for correo in ("ana@gmail.com", "ana@utc.edu.ec"):
            with self.subTest(correo=correo):
                form = PacienteRegistroForm(data={**datos, "correo": correo})
                self.assertTrue(form.is_valid(), form.errors)

    def test_paciente_model_fields_have_ten_digit_constraints(self):
        for field_name in ("cedula", "celular"):
            field = Paciente._meta.get_field(field_name)
            self.assertEqual(field.max_length, 10)
            with self.assertRaises(ValidationError):
                field.clean("123", None)
            field.clean("1234567890", None)

    def test_paciente_form_date_of_birth_uses_date_input(self):
        form = PacienteRegistroForm()
        self.assertEqual(
            form.fields["fecha_nacimiento"].widget.input_type,
            "date",
        )

    def test_doctor_contact_form_validation(self):
        datos = {
            "username": "medico-contacto",
            "password": "Unica!ClaveSegura2026",
            "first_name": "Luis",
            "last_name": "Medico",
            "especialidad": "Cardiología",
            "correo": "luis@utc.edu.ec",
            "celular": "0991234567",
        }
        form = MedicoRegistroForm(data=datos)
        self.assertTrue(form.is_valid(), form.errors)

        for celular in ("099123456", "09912345678", "09912abc67"):
            with self.subTest(celular=celular):
                form = MedicoRegistroForm(data={**datos, "celular": celular})
                self.assertFalse(form.is_valid())
                self.assertIn("celular", form.errors)

        form = MedicoRegistroForm(data={**datos, "correo": "sin-correo-valido"})
        self.assertFalse(form.is_valid())
        self.assertIn("correo", form.errors)

    def test_paciente_age_calculation(self):
        paciente = Paciente(fecha_nacimiento=date(2000, 7, 1))
        hoy = timezone.localdate()
        expected_age = hoy.year - 2000 - ((hoy.month, hoy.day) < (7, 1))
        self.assertEqual(paciente.edad, expected_age)

        paciente.fecha_nacimiento = None
        self.assertEqual(paciente.edad, "No registrada")

    def test_medico_especialidad_is_a_select_with_allowed_choices(self):
        form = MedicoRegistroForm()

        self.assertIsInstance(form.fields["especialidad"].widget, Select)
        self.assertIn(
            ("Cardiología", "Cardiología"),
            form.fields["especialidad"].choices,
        )

        form = MedicoRegistroForm(
            data={
                "username": "medico-invalido",
                "password": "Unica!ClaveSegura2026",
                "first_name": "Luis",
                "last_name": "Medico",
                "especialidad": "Especialidad inválida",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("especialidad", form.errors)


class BaseNavbarRoleTests(TestCase):
    def test_navbar_role_filter_detects_group_membership(self):
        user = get_user_model().objects.create_user(
            username="doctor-navbar",
            password="DoctorNavbar!123",
            first_name="Lucía",
            last_name="Médica",
        )
        doctor_group, _ = Group.objects.get_or_create(name="Medicos")
        user.groups.add(doctor_group)

        rendered = Template(
            '{% load user_roles %}'
            '{% if user|has_group:"Medicos" %}'
            '🩺 Doctor(a): {{ user.first_name }} {{ user.last_name }}'
            '{% endif %}'
        ).render(Context({"user": user}))

        self.assertIn("Doctor(a): Lucía Médica", rendered)


class PanelMedicoTests(TestCase):
    def test_medico_solo_atiende_su_cita_y_actualiza_estado(self):
        usuario_medico = get_user_model().objects.create_user(
            username="medico-panel",
            password="Unica!ClaveSegura2026",
        )
        usuario_paciente = get_user_model().objects.create_user(
            username="paciente-panel",
            password="Unica!ClaveSegura2026",
        )
        medico = Medico.objects.create(
            user=usuario_medico,
            especialidad="Medicina General",
        )
        paciente = Paciente.objects.create(
            user=usuario_paciente,
            cedula="9876543210",
            celular="0991234567",
        )
        cita = Cita.objects.create(
            id_paciente=paciente,
            id_medico=medico,
            fecha=timezone.localdate(),
            hora="10:00",
        )

        self.client.force_login(usuario_medico)
        response = self.client.get(reverse("panel_medico"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "paciente-panel")

        response = self.client.post(
            reverse("panel_medico"),
            {
                "registrar_atencion": "1",
                "cita_id": str(cita.pk),
                f"cita-{cita.pk}-motivo_consulta": "Dolor de cabeza",
                f"cita-{cita.pk}-diagnostico_clinico": "Diagnóstico de prueba",
                f"cita-{cita.pk}-tratamiento": "Tratamiento de prueba",
                f"cita-{cita.pk}-observaciones": "",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('panel_medico')}?paciente_id={paciente.pk}&cita_id={cita.pk}",
        )
        self.assertIn(
            "Atención médica registrada con éxito.",
            [message.message for message in response.wsgi_request._messages],
        )
        cita.refresh_from_db()
        self.assertEqual(cita.estado, Cita.Estado.ATENDIDA)
        self.assertTrue(Atencion.objects.filter(id_cita=cita).exists())
        atencion = Atencion.objects.get(id_cita=cita)
        self.assertEqual(atencion.motivo_consulta, "Dolor de cabeza")
        self.assertIn(
            "Atención médica registrada con éxito.",
            [message.message for message in response.wsgi_request._messages],
        )


class PanelAdministrativoTests(TestCase):
    def test_administrador_puede_editar_medico_y_sus_datos_de_usuario(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-medico-edicion",
            password="AdminMedico!123",
            email="admin-medico@example.com",
        )
        medico_user = get_user_model().objects.create_user(
            username="medico-edicion",
            password="MedicoEdicion!123",
            first_name="Luis",
            last_name="Antes",
        )
        medico = Medico.objects.create(
            user=medico_user,
            especialidad="Medicina General",
        )
        url = reverse("editar_medico", args=[medico.pk])
        self.client.force_login(admin)

        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)
        self.assertIsInstance(get_response.context["formulario"], MedicoEdicionForm)

        response = self.client.post(
            url,
            {
                "username": "medico-actualizado",
                "first_name": "Luis Alberto",
                "last_name": "Después",
                "especialidad": "Cardiología",
                "correo": "luis@utc.edu.ec",
                "celular": "0997654321",
            },
        )

        self.assertRedirects(response, reverse("panel_administrativo"))
        medico.refresh_from_db()
        medico.user.refresh_from_db()
        self.assertEqual(medico.especialidad, "Cardiología")
        self.assertEqual(medico.correo, "luis@utc.edu.ec")
        self.assertEqual(medico.celular, "0997654321")
        self.assertEqual(medico.user.username, "medico-actualizado")
        self.assertEqual(medico.user.first_name, "Luis Alberto")
        self.assertEqual(medico.user.last_name, "Después")

    def test_administrador_elimina_paciente_y_usuario_asociado(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-paciente-eliminar",
            password="AdminPaciente!123",
            email="admin-paciente@example.com",
        )
        paciente_user = get_user_model().objects.create_user(
            username="paciente-eliminar",
            password="PacienteEliminar!123",
        )
        paciente = Paciente.objects.create(
            user=paciente_user,
            cedula="1357913579",
            celular="0991234567",
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("eliminar_paciente", args=[paciente.pk])
        )

        self.assertRedirects(response, reverse("panel_administrativo"))
        self.assertFalse(Paciente.objects.filter(pk=paciente.pk).exists())
        self.assertFalse(
            get_user_model().objects.filter(pk=paciente_user.pk).exists()
        )

    def test_administrador_elimina_medico_y_usuario_asociado(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-medico-eliminar",
            password="AdminMedicoEliminar!123",
            email="admin-medico-eliminar@example.com",
        )
        medico_user = get_user_model().objects.create_user(
            username="medico-eliminar",
            password="MedicoEliminar!123",
        )
        medico = Medico.objects.create(
            user=medico_user,
            especialidad="Medicina General",
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("eliminar_medico", args=[medico.pk])
        )

        self.assertRedirects(response, reverse("panel_administrativo"))
        self.assertFalse(Medico.objects.filter(pk=medico.pk).exists())
        self.assertFalse(get_user_model().objects.filter(pk=medico_user.pk).exists())

    def test_eliminaciones_requieren_post_y_rol_administrativo(self):
        patient_user = get_user_model().objects.create_user(
            username="paciente-no-admin-delete",
            password="PacienteNoAdmin!123",
        )
        patient = Paciente.objects.create(
            user=patient_user,
            cedula="2468024680",
            celular="0991234567",
        )
        self.client.force_login(patient_user)

        get_response = self.client.get(
            reverse("eliminar_paciente", args=[patient.pk])
        )
        post_response = self.client.post(
            reverse("eliminar_paciente", args=[patient.pk])
        )

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.assertTrue(Paciente.objects.filter(pk=patient.pk).exists())

        admin = get_user_model().objects.create_superuser(
            username="admin-delete-method",
            password="AdminDeleteMethod!123",
            email="admin-delete-method@example.com",
        )
        self.client.force_login(admin)
        self.assertEqual(
            self.client.get(
                reverse("eliminar_paciente", args=[patient.pk])
            ).status_code,
            405,
        )

    def test_administrador_puede_editar_paciente_y_sus_datos_de_usuario(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-edicion",
            password="AdminEdicion!123",
            email="admin-edicion@example.com",
        )
        paciente_user = get_user_model().objects.create_user(
            username="paciente-edicion",
            password="PacienteEdicion!123",
            first_name="Ana",
            last_name="Antes",
        )
        paciente = Paciente.objects.create(
            user=paciente_user,
            cedula="1234567890",
            celular="0991234567",
            sexo="Femenino",
            correo="ana@example.com",
        )
        url = reverse("editar_paciente", args=[paciente.pk])
        self.client.force_login(admin)

        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)
        self.assertIsInstance(
            get_response.context["formulario"],
            PacienteEdicionForm,
        )

        response = self.client.post(
            url,
            {
                "username": "paciente-actualizado",
                "first_name": "Ana María",
                "last_name": "Después",
                "cedula": "1234567890",
                "celular": "0997654321",
                "sexo": "Femenino",
                "correo": "ana.actualizada@example.com",
            },
        )

        self.assertRedirects(response, reverse("panel_administrativo"))
        paciente.refresh_from_db()
        paciente.user.refresh_from_db()
        self.assertEqual(paciente.celular, "0997654321")
        self.assertEqual(paciente.correo, "ana.actualizada@example.com")
        self.assertEqual(paciente.user.username, "paciente-actualizado")
        self.assertEqual(paciente.user.first_name, "Ana María")
        self.assertEqual(paciente.user.last_name, "Después")

    def test_edicion_de_paciente_requiere_rol_administrativo(self):
        paciente_user = get_user_model().objects.create_user(
            username="paciente-protegido",
            password="PacienteProtegido!123",
        )
        paciente = Paciente.objects.create(
            user=paciente_user,
            cedula="1234567890",
            celular="0991234567",
        )

        self.client.force_login(paciente_user)
        response = self.client.get(
            reverse("editar_paciente", args=[paciente.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_ruta_raiz_redirige_segun_rol_y_no_devuelve_403(self):
        user_model = get_user_model()
        admin = user_model.objects.create_superuser(
            username="router-admin",
            password="Unica!ClaveSegura2026",
            email="router-admin@example.com",
        )
        doctor_user = user_model.objects.create_user(
            username="router-doctor",
            password="Unica!ClaveSegura2026",
        )
        Medico.objects.create(
            user=doctor_user,
            especialidad="Medicina General",
        )
        patient_user = user_model.objects.create_user(
            username="router-patient",
            password="Unica!ClaveSegura2026",
        )
        Paciente.objects.create(
            user=patient_user,
            cedula="1234509876",
            celular="0991234567",
        )

        response = self.client.get(reverse("inicio"))
        self.assertRedirects(response, reverse("login"))

        for user, destination in (
            (admin, "panel_administrativo"),
            (doctor_user, "panel_medico"),
            (patient_user, "panel_paciente"),
        ):
            with self.subTest(role=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("inicio"))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse(destination))

    def test_root_uses_group_for_role_routing(self):
        doctor_user = get_user_model().objects.create_user(
            username="router-group-doctor",
            password="Unica!ClaveSegura2026",
        )
        doctor_group, _ = Group.objects.get_or_create(name="Medicos")
        doctor_user.groups.add(doctor_group)
        self.client.force_login(doctor_user)

        response = self.client.get(reverse("inicio"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("panel_medico"))

    def test_submit_agendar_cita_bloquea_paciente_con_cita_confirmada(self):
        usuario_admin = get_user_model().objects.create_superuser(
            username="admin-citas",
            password="Unica!ClaveSegura2026",
            email="admin@example.com",
        )
        usuario_medico = get_user_model().objects.create_user(
            username="medico-citas",
            password="Unica!ClaveSegura2026",
        )
        usuario_paciente = get_user_model().objects.create_user(
            username="paciente-citas",
            password="Unica!ClaveSegura2026",
        )
        medico = Medico.objects.create(
            user=usuario_medico,
            especialidad="Medicina General",
        )
        paciente = Paciente.objects.create(
            user=usuario_paciente,
            cedula="1234509876",
            celular="0991234567",
        )
        Cita.objects.create(
            id_paciente=paciente,
            id_medico=medico,
            fecha=timezone.localdate(),
            hora="11:00",
        )

        self.client.force_login(usuario_admin)
        response = self.client.post(
            reverse("panel_administrativo"),
            {
                "agendar_cita": "1",
                "id_paciente": str(paciente.pk),
                "id_medico": str(medico.pk),
                "fecha": timezone.localdate().isoformat(),
                "hora": "11:00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Error: El paciente ya tiene otra cita programada en esa fecha y hora exacta.",
        )
        self.assertEqual(Cita.objects.count(), 1)

    def test_submit_agendar_cita_bloquea_medico_con_cita_confirmada(self):
        usuario_admin = get_user_model().objects.create_superuser(
            username="admin-medico-ocupado",
            password="AdminMedicoOcupado!123",
            email="admin-medico-ocupado@example.com",
        )
        medico_user = get_user_model().objects.create_user(
            username="medico-ocupado",
            password="MedicoOcupado!123",
        )
        paciente_users = [
            get_user_model().objects.create_user(
                username=f"paciente-horario-{index}",
                password="PacienteHorario!123",
            )
            for index in range(2)
        ]
        medico = Medico.objects.create(
            user=medico_user,
            especialidad="Medicina General",
        )
        pacientes = [
            Paciente.objects.create(
                user=user,
                cedula=f"12345098{index:02d}",
                celular="0991234567",
            )
            for index, user in enumerate(paciente_users)
        ]
        fecha = timezone.localdate()
        Cita.objects.create(
            id_paciente=pacientes[0],
            id_medico=medico,
            fecha=fecha,
            hora="11:00",
        )

        self.client.force_login(usuario_admin)
        response = self.client.post(
            reverse("panel_administrativo"),
            {
                "action": "agendar_cita",
                "id_paciente": str(pacientes[1].pk),
                "id_medico": str(medico.pk),
                "fecha": fecha.isoformat(),
                "hora": "11:00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Error: El médico seleccionado ya tiene una cita ocupada en ese horario.",
        )
        self.assertEqual(Cita.objects.count(), 1)

    def test_cita_cancelada_no_cuenta_como_conflicto_de_paciente(self):
        usuario_admin = get_user_model().objects.create_superuser(
            username="admin-cita-cancelada",
            password="AdminCitaCancelada!123",
            email="admin-cita-cancelada@example.com",
        )
        medico_user = get_user_model().objects.create_user(
            username="medico-cita-cancelada",
            password="MedicoCitaCancelada!123",
        )
        paciente_user = get_user_model().objects.create_user(
            username="paciente-cita-cancelada",
            password="PacienteCitaCancelada!123",
        )
        other_patient_user = get_user_model().objects.create_user(
            username="paciente-nuevo-horario",
            password="PacienteNuevoHorario!123",
        )
        medico = Medico.objects.create(
            user=medico_user,
            especialidad="Medicina General",
        )
        paciente = Paciente.objects.create(
            user=paciente_user,
            cedula="7777777701",
            celular="0991234567",
        )
        other_patient = Paciente.objects.create(
            user=other_patient_user,
            cedula="7777777702",
            celular="0991234567",
        )
        fecha = timezone.localdate()
        Cita.objects.create(
            id_paciente=paciente,
            id_medico=medico,
            fecha=fecha,
            hora="11:00",
            estado=Cita.Estado.CANCELADA,
        )

        self.client.force_login(usuario_admin)
        response = self.client.post(
            reverse("panel_administrativo"),
            {
                "action": "agendar_cita",
                "id_paciente": str(other_patient.pk),
                "id_medico": str(medico.pk),
                "fecha": fecha.isoformat(),
                "hora": "11:00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cita agendada correctamente.")
        self.assertEqual(Cita.objects.filter(estado=Cita.Estado.CONFIRMADA).count(), 1)

    def test_panel_administrativo_registra_medico_y_muestra_estadisticas(self):
        usuario_admin = get_user_model().objects.create_superuser(
            username="admin-medicos",
            password="Unica!ClaveSegura2026",
            email="admin-medicos@example.com",
        )
        self.client.force_login(usuario_admin)

        response = self.client.post(
            reverse("panel_administrativo"),
            {
                "action": "registrar_medico",
                "username": "medico-nuevo",
                "password": "Otra!ClaveSegura2026",
                "first_name": "Elena",
                "last_name": "Doctora",
                "especialidad": "Pediatría",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Medico.objects.count(), 1)
        self.assertEqual(response.context["total_doctores"], 1)
        self.assertEqual(response.context["total_pacientes"], 0)
        self.assertEqual(response.context["citas_hoy"], 0)
        doctor_user = get_user_model().objects.get(username="medico-nuevo")
        self.assertTrue(doctor_user.groups.filter(name="Medicos").exists())


class PanelMedicoHistoriaTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.doctor_user = user_model.objects.create_user(
            username="medico-historia",
            password="Unica!ClaveSegura2026",
        )
        self.patient_user = user_model.objects.create_user(
            username="paciente-historia",
            password="Unica!ClaveSegura2026",
        )
        self.medico = Medico.objects.create(
            user=self.doctor_user,
            especialidad="Medicina General",
        )
        self.paciente = Paciente.objects.create(
            user=self.patient_user,
            cedula="2345678901",
            celular="0991234567",
        )
        self.cita_hoy = Cita.objects.create(
            id_paciente=self.paciente,
            id_medico=self.medico,
            fecha=timezone.localdate(),
            hora="09:00",
        )
        self.cita_anterior = Cita.objects.create(
            id_paciente=self.paciente,
            id_medico=self.medico,
            fecha=timezone.localdate() - timedelta(days=2),
            hora="09:00",
            estado=Cita.Estado.ATENDIDA,
        )
        Atencion.objects.create(
            id_cita=self.cita_anterior,
            motivo_consulta="Control",
            diagnostico_clinico="Evolución estable",
            tratamiento="Continuar plan",
            observaciones="Revisar en próxima cita",
        )

    def test_panel_muestra_historial_completo_del_paciente_autorizado(self):
        self.client.force_login(self.doctor_user)

        response = self.client.get(
            reverse("panel_medico"),
            {"paciente_id": self.paciente.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["historial_medico"]), 1)
        self.assertContains(response, "Evolución estable")
        self.assertContains(response, "Control")
        self.assertEqual(response.context["paciente_historia"], self.paciente)
        self.assertEqual(response.context["cita_seleccionada"], self.cita_hoy)
        self.assertContains(response, "No registrada")
        self.assertContains(response, "Finalizar Consulta y Guardar Historial")

    def test_panel_rechaza_historial_de_paciente_sin_relacion_medica(self):
        otro_usuario = get_user_model().objects.create_user(
            username="paciente-ajeno",
            password="Unica!ClaveSegura2026",
        )
        paciente_ajeno = Paciente.objects.create(
            user=otro_usuario,
            cedula="2345678902",
            celular="0997654321",
        )
        self.client.force_login(self.doctor_user)

        response = self.client.get(
            reverse("panel_medico"),
            {"paciente_id": paciente_ajeno.pk},
        )

        self.assertEqual(response.status_code, 403)

    def test_medico_puede_registrar_paciente_desde_su_panel(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("panel_medico"),
            {
                "action": "registrar_paciente",
                "username": "paciente-nuevo",
                "password": "Otra!ClaveSegura2026",
                "first_name": "Mario",
                "last_name": "Nuevo",
                "cedula": "3456789012",
                "celular": "0991112233",
                "sexo": "Masculino",
                "correo": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Paciente.objects.filter(user__username="paciente-nuevo").exists()
        )
