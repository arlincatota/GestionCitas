from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import transaction

from .models import (
    Atencion,
    Cita,
    ESPECIALIDADES_CHOICES,
    Medico,
    Paciente,
    SEXO_CHOICES,
    cedula_validator,
    telefono_validator,
)

User = get_user_model()

MENSAJE_CORREO_INVALIDO = (
    "Ingrese una dirección de correo electrónico válida que contenga @ y un dominio."
)


class CorreoField(forms.EmailField):
    default_validators = [EmailValidator(message=MENSAJE_CORREO_INVALIDO)]


class _RegistroUsuarioForm(forms.Form):
    username = forms.CharField(max_length=150, label="Usuario")
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput,
    )
    first_name = forms.CharField(max_length=150, label="Nombres")
    last_name = forms.CharField(max_length=150, label="Apellidos")

    profile_model = None
    group_name = ""
    profile_fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select"
                if isinstance(field.widget, forms.Select)
                else "form-control"
            )

    def clean_username(self):
        username = self.cleaned_data["username"]
        username_field = User._meta.get_field(User.USERNAME_FIELD)
        try:
            username_field.clean(username, None)
        except ValidationError as error:
            raise forms.ValidationError(error.messages) from error
        if User._default_manager.filter(
            **{User.USERNAME_FIELD: username}
        ).exists():
            raise forms.ValidationError("Este usuario ya está registrado.")
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        usuario = User(
            **{
                User.USERNAME_FIELD: self.data.get("username", ""),
                "first_name": self.data.get("first_name", ""),
                "last_name": self.data.get("last_name", ""),
            }
        )
        try:
            validate_password(password, usuario)
        except ValidationError as error:
            raise forms.ValidationError(error.messages) from error
        return password

    def save(self):
        if not self.is_valid():
            raise ValueError("No se puede guardar un formulario inválido.")

        with transaction.atomic():
            usuario = User(
                **{
                    User.USERNAME_FIELD: self.cleaned_data["username"],
                    "first_name": self.cleaned_data["first_name"],
                    "last_name": self.cleaned_data["last_name"],
                }
            )
            usuario.set_password(self.cleaned_data["password"])
            usuario.save()

            grupo, _ = Group.objects.get_or_create(name=self.group_name)
            usuario.groups.add(grupo)

            datos_perfil = {
                field: self.cleaned_data[field]
                for field in self.profile_fields
            }
            return self.profile_model.objects.create(
                user=usuario,
                **datos_perfil,
            )


class PacienteRegistroForm(_RegistroUsuarioForm):
    fecha_nacimiento = forms.DateField(
        label="Fecha de nacimiento",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    sexo = forms.ChoiceField(
        choices=(("", "Seleccione..."), *SEXO_CHOICES),
        label="Sexo",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    correo = CorreoField(
        label="Correo electrónico",
        required=False,
        error_messages={
            "invalid": MENSAJE_CORREO_INVALIDO,
        },
    )
    cedula = forms.CharField(
        max_length=10,
        label="Cédula",
        strip=False,
        validators=[cedula_validator],
        error_messages={
            "max_length": "La cédula debe tener exactamente 10 dígitos numéricos."
        },
    )
    celular = forms.CharField(
        max_length=10,
        label="Teléfono",
        strip=False,
        validators=[telefono_validator],
        error_messages={
            "max_length": "El teléfono debe tener exactamente 10 dígitos numéricos."
        },
    )

    profile_model = Paciente
    group_name = "Pacientes"
    profile_fields = (
        "cedula",
        "celular",
        "sexo",
        "correo",
        "fecha_nacimiento",
    )


class PacienteEdicionForm(forms.ModelForm):
    username = forms.CharField(max_length=150, label="Usuario")
    first_name = forms.CharField(max_length=150, label="Nombres")
    last_name = forms.CharField(max_length=150, label="Apellidos")

    class Meta:
        model = Paciente
        fields = (
            "cedula",
            "celular",
            "sexo",
            "correo",
            "fecha_nacimiento",
        )
        labels = {
            "cedula": "Cédula",
            "celular": "Teléfono",
            "sexo": "Sexo",
            "correo": "Correo electrónico",
            "fecha_nacimiento": "Fecha de nacimiento",
        }
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
            "sexo": forms.Select(
                choices=(("", "Seleccione..."), *SEXO_CHOICES),
                attrs={"class": "form-select"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sexo"].choices = (("", "Seleccione..."), *SEXO_CHOICES)
        self.fields["sexo"].required = True
        self.fields["correo"].required = False
        if self.instance and self.instance.pk:
            self.fields["username"].initial = getattr(
                self.instance.user,
                User.USERNAME_FIELD,
            )
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select"
                if isinstance(field.widget, forms.Select)
                else "form-control"
            )

    def clean_username(self):
        username = self.cleaned_data["username"]
        username_field = User._meta.get_field(User.USERNAME_FIELD)
        try:
            username_field.clean(username, self.instance.user)
        except ValidationError as error:
            raise forms.ValidationError(error.messages) from error
        if User._default_manager.filter(
            **{User.USERNAME_FIELD: username}
        ).exclude(pk=self.instance.user_id).exists():
            raise forms.ValidationError("Este usuario ya está registrado.")
        return username

    def save(self, commit=True):
        paciente = super().save(commit=False)
        usuario = paciente.user
        setattr(usuario, User.USERNAME_FIELD, self.cleaned_data["username"])
        usuario.first_name = self.cleaned_data["first_name"]
        usuario.last_name = self.cleaned_data["last_name"]
        if commit:
            with transaction.atomic():
                usuario.save()
                paciente.save()
        return paciente


class MedicoRegistroForm(_RegistroUsuarioForm):
    especialidad = forms.ChoiceField(
        choices=ESPECIALIDADES_CHOICES,
        label="Especialidad",
    )
    correo = CorreoField(
        label="Correo electrónico",
        required=False,
        error_messages={"invalid": MENSAJE_CORREO_INVALIDO},
    )
    celular = forms.CharField(
        max_length=10,
        label="Teléfono",
        required=False,
        strip=False,
        validators=[telefono_validator],
        error_messages={
            "max_length": "El teléfono debe tener exactamente 10 dígitos numéricos."
        },
    )

    profile_model = Medico
    group_name = "Medicos"
    profile_fields = ("especialidad", "correo", "celular")


class MedicoEdicionForm(forms.ModelForm):
    username = forms.CharField(max_length=150, label="Usuario")
    first_name = forms.CharField(max_length=150, label="Nombres")
    last_name = forms.CharField(max_length=150, label="Apellidos")

    class Meta:
        model = Medico
        fields = ("especialidad", "correo", "celular")
        labels = {
            "especialidad": "Especialidad",
            "correo": "Correo electrónico",
            "celular": "Teléfono",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["username"].initial = getattr(
                self.instance.user,
                User.USERNAME_FIELD,
            )
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select"
                if isinstance(field.widget, forms.Select)
                else "form-control"
            )

    def clean_username(self):
        username = self.cleaned_data["username"]
        username_field = User._meta.get_field(User.USERNAME_FIELD)
        try:
            username_field.clean(username, self.instance.user)
        except ValidationError as error:
            raise forms.ValidationError(error.messages) from error
        if User._default_manager.filter(
            **{User.USERNAME_FIELD: username}
        ).exclude(pk=self.instance.user_id).exists():
            raise forms.ValidationError("Este usuario ya está registrado.")
        return username

    def save(self, commit=True):
        medico = super().save(commit=False)
        usuario = medico.user
        setattr(usuario, User.USERNAME_FIELD, self.cleaned_data["username"])
        usuario.first_name = self.cleaned_data["first_name"]
        usuario.last_name = self.cleaned_data["last_name"]
        if commit:
            with transaction.atomic():
                usuario.save()
                medico.save()
        return medico


class CitaAgendaForm(forms.ModelForm):
    class Meta:
        model = Cita
        fields = ("id_paciente", "id_medico", "fecha", "hora")
        labels = {
            "id_paciente": "Paciente",
            "id_medico": "Médico",
            "fecha": "Fecha",
            "hora": "Hora",
        }
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "hora": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["id_paciente"].queryset = Paciente.objects.select_related("user")
        self.fields["id_medico"].queryset = Medico.objects.select_related("user")
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(
                field.widget, forms.Select
            ) else "form-control"


class AtencionClinicaForm(forms.ModelForm):
    class Meta:
        model = Atencion
        fields = (
            "motivo_consulta",
            "diagnostico_clinico",
            "tratamiento",
            "observaciones",
        )
        labels = {
            "motivo_consulta": "Motivo de consulta",
            "diagnostico_clinico": "Diagnóstico",
            "tratamiento": "Tratamiento / Receta",
            "observaciones": "Observaciones",
        }
        widgets = {
            "motivo_consulta": forms.Textarea(attrs={"rows": 3}),
            "diagnostico_clinico": forms.Textarea(attrs={"rows": 5}),
            "tratamiento": forms.Textarea(attrs={"rows": 5}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motivo_consulta"].required = True
        self.fields["observaciones"].required = False
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
