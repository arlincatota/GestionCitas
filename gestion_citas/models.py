from django.conf import settings
from django.core.validators import EmailValidator, RegexValidator
from django.db import models
from django.utils import timezone


cedula_validator = RegexValidator(
    regex=r"\A[0-9]{10}\Z",
    message="La cédula debe tener exactamente 10 dígitos numéricos.",
)
telefono_validator = RegexValidator(
    regex=r"\A[0-9]{10}\Z",
    message="El teléfono debe tener exactamente 10 dígitos numéricos.",
)


ESPECIALIDADES_CHOICES = [
    ("Medicina General", "Medicina General"),
    ("Pediatría", "Pediatría"),
    ("Cardiología", "Cardiología"),
    ("Ginecología", "Ginecología"),
    ("Dermatología", "Dermatología"),
    ("Odontología", "Odontología"),
]

SEXO_CHOICES = [
    ("Masculino", "Masculino"),
    ("Femenino", "Femenino"),
]


class Paciente(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="paciente",
    )
    fecha_nacimiento = models.DateField(null=True, blank=True)
    cedula = models.CharField(
        max_length=10,
        unique=True,
        validators=[cedula_validator],
    )
    celular = models.CharField(
        max_length=10,
        validators=[telefono_validator],
    )
    sexo = models.CharField(
        max_length=10,
        choices=SEXO_CHOICES,
        blank=True,
        null=True,
    )
    correo = models.EmailField(blank=True, null=True)

    @property
    def edad(self):
        if self.fecha_nacimiento is None:
            return "No registrada"
        hoy = timezone.localdate()
        return (
            hoy.year
            - self.fecha_nacimiento.year
            - (
                (hoy.month, hoy.day)
                < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
        )

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()


class Medico(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="medico",
    )
    especialidad = models.CharField(
        max_length=100,
        choices=ESPECIALIDADES_CHOICES,
    )
    correo = models.EmailField(
        null=True,
        blank=True,
        validators=[
            EmailValidator(
                message="Ingrese una dirección de correo electrónico válida que contenga @ y un dominio."
            )
        ],
    )
    celular = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        validators=[telefono_validator],
    )

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.get_username()}"


class Cita(models.Model):
    class Estado(models.TextChoices):
        CONFIRMADA = "Confirmada", "Confirmada"
        CANCELADA = "Cancelada", "Cancelada"
        ATENDIDA = "Atendida", "Atendida"

    id_paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    id_medico = models.ForeignKey(Medico, on_delete=models.CASCADE)
    fecha = models.DateField()
    hora = models.TimeField()
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.CONFIRMADA,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("id_medico", "fecha", "hora"),
                condition=models.Q(estado="Confirmada"),
                name="unique_confirmed_doctor_appointment_slot",
            ),
        ]

    def __str__(self):
        return f"Cita de {self.id_paciente} con {self.id_medico} el {self.fecha}"


class Atencion(models.Model):
    id_cita = models.OneToOneField(Cita, on_delete=models.CASCADE)
    motivo_consulta = models.TextField(blank=True)
    diagnostico_clinico = models.TextField()
    tratamiento = models.TextField()
    observaciones = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Atención de la cita {self.id_cita_id}"
