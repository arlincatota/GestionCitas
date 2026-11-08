from django.contrib import admin

from .models import Atencion, Cita, Medico, Paciente

admin.site.register((Paciente, Medico, Cita, Atencion))
