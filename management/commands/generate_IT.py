import math
from django.core.management.base import BaseCommand
from fits.models import ISOToleranceITClass, Standards

class Command(BaseCommand):
    help = "Generate ISO 286 tolerance table and populate IT-ISOTolerance model"

    def handle(self, *args, **options):
        # Beispiel: Standard setzen (du hast vermutlich schon ein Standards-Objekt)
        standard, _ = Standards.objects.get_or_create(app_name='fits', title="ISO 286-1:2010")

        # Nennmaßbereiche (wie in ISO 286 definiert)
        nominal_ranges = [
            (0.001, 3), (3, 6), (6, 10), (10, 18), (18, 30), (30, 50),
            (50, 80), (80, 120), (120, 180), (180, 250), (250, 315),
            (315, 400), (400, 500)
        ]

        # Multiplikatoren k für IT-Klassen
        multipliers = {
            'IT5': 7, 'IT6': 10, 'IT7': 16, 'IT8': 25, 'IT9': 40,
            'IT10': 64, 'IT11': 100, 'IT12': 160, 'IT13': 250,
            'IT14': 400, 'IT15': 640, 'IT16': 1000,
            'IT17': 1600, 'IT18': 2500,
        }
        # Sonderfälle IT1–IT4 lassen wir für Einfachheit erst mal aus

        for nominal_min, nominal_max in nominal_ranges:
            # geometrisches Mittel
            D = math.sqrt(nominal_min * nominal_max)

            # Einheitstoleranz i in µm
            i = 0.45 * (D ** (1/3)) + 0.001 * D

            for it_class, k in multipliers.items():
                tol_value = k * i  # in µm

                ISOToleranceITClass.objects.update_or_create(
                    standards=standard,
                    nominal_size_min=nominal_min,
                    nominal_size_max=nominal_max,
                    tolerance_class=it_class,
                    defaults={
                        'tolerance_value': int(tol_value),  # in µm als Integer speichern
                        'description': f"{it_class} für {nominal_min}–{nominal_max} mm"
                    }
                )

        self.stdout.write(self.style.SUCCESS("ISO 286 Toleranzen erfolgreich generiert!"))
