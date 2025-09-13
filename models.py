import re
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.forms import CharField
from django.utils.translation import gettext as _
from main.models import Standards 
from django.db.models import CharField, IntegerField, Q, F
from django.db.models.functions import Substr, Length, Cast
from .constants import TOLERANCE_CLASSES

class ISOManager(models.Manager):

    def all(self, nominal_size=None, isBore=True):
        """Get distinct tolerance classes for a given nominal size."""
        if nominal_size is not None:
            if self.model.__name__ == "ISOToleranceITClass":
                return self.filter(
                    nominal_size_min__lt=nominal_size,
                    nominal_size_max__gte=nominal_size
                ).annotate(
                    tolerance_number=Cast(
                        Substr('tolerance_class', 3, Length('tolerance_class') - 2),
                        output_field=IntegerField()
                    ),
                    it_class=Cast(F('tolerance_class'), output_field=CharField()),
                    it_value=F('tolerance_value')
                ).values('it_class', 'it_value'
                ).distinct().order_by('tolerance_number')
            
            else:  # ISOToleranceClass
                    # Regex für nur Buchstaben (ohne Zahlen)
                if isBore:
                    # Bohrung: Beginnt mit Großbuchstaben (A-Z)
                    # Regex für Bohrung: Beginnt mit Großbuchstaben (A-Z), gefolgt von beliebigen Zeichen außer Zahlen
                    # ^[A-Z]+     -> Der String beginnt mit einem oder mehreren Großbuchstaben
                    # [^0-9]*$    -> Danach folgen beliebige Zeichen, aber keine Ziffern (0-9), bis zum Ende des Strings
                    # Regex für ISO 286: Beginnt mit Großbuchstaben, optional gefolgt von weiteren Buchstaben, dann optional Zahlen
                    # Beispiel: "H", "H7", "G6", "ZC4"
                    regex_pattern = r'^[A-Z]+[A-Z]*$'
                else:
                    # Welle: Beginnt mit Kleinbuchstaben (a-z)
                    regex_pattern = r'^[a-z]+[a-z]*$'

                return self.filter(
                    nominal_size_min__lt=nominal_size,
                    nominal_size_max__gte=nominal_size
                ).filter(
                    tolerance_class__regex=regex_pattern
                ).values('tolerance_class'
                ).distinct().order_by('tolerance_class'
                )
        
        # If no nominal size is provided, return all records
        return self.all()
    
    def get_grades(self, nominal_size=None, tolerance=None, isBore=True):
        """Get distinct tolerance classes for a given nominal size."""
        if isBore:
            # Bohrung: Beginnt mit Großbuchstaben (A-Z)
            # Regex für Bohrung: Beginnt mit Großbuchstaben (A-Z), gefolgt von beliebigen Zeichen außer Zahlen
            # ^[A-Z]+     -> Der String beginnt mit einem oder mehreren Großbuchstaben
            # [^0-9]*$    -> Danach folgen beliebige Zeichen, aber keine Ziffern (0-9), bis zum Ende des Strings
            # Regex für ISO 286: Beginnt mit Großbuchstaben, optional gefolgt von weiteren Buchstaben, dann optional Zahlen
            # Beispiel: "H", "H7", "G6", "ZC4"
            regex_pattern = r'^[A-Z]+[A-Z]*[0-9]*$'
        else:
            # Welle: Beginnt mit Kleinbuchstaben (a-z)
            regex_pattern = r'^[a-z]+[a-z]*[0-9]*$'

        if nominal_size is not None and tolerance is not None:
            lst = self.filter(
                nominal_size_min__lte=nominal_size,
                nominal_size_max__gte=nominal_size,
                tolerance_class=tolerance
            ).values_list('tolerance_grade', flat=True).distinct()
            lst = [int(x) for x in lst if x is not None and str(x).isdigit()]
            lst.sort()
            return lst
        return self.values_list('tolerance_class', flat=True).distinct()

    def get_value(self, nominal_size=None, tolerance_class=None, tolerance_grade=None):
        """Get the tolerance value for a given nominal size and tolerance class."""
        if nominal_size is not None and tolerance_class is not None:    
            value = self.filter(
                nominal_size_min__lte=nominal_size,
                nominal_size_max__gte=nominal_size,
                tolerance_class=tolerance_class,
                tolerance_grade=tolerance_grade
            ).values('tolerance_min', 'tolerance_max').distinct().order_by('tolerance_class')
            # Raise value error if more than one value is found
            print(f"DEBUG: {value.count()} values found for nominal size {nominal_size}, class {tolerance_class}, grade {tolerance_grade}")
            if value.count() > 1:
                raise ValueError("Multiple tolerance values found")
            if value.exists():
                return {
                    'tolerance_min': value[0]['tolerance_min'],
                    'tolerance_max': value[0]['tolerance_max']
                }
# this class represents ISO286 tolerances table
class ISOToleranceITClass(models.Model):
    
    standards = models.ForeignKey(
        Standards,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    nominal_size_min = models.IntegerField(
        help_text="Lower limit of nominal size range (mm)"
        )
    nominal_size_max = models.IntegerField(
        help_text="Upper limit of nominal size range (mm)"
        )
    tolerance_class = models.CharField(
        max_length=4,
        choices=TOLERANCE_CLASSES
        )
    tolerance_value = models.FloatField(
        help_text="Tolerance value in microns"
        )
    description = models.TextField(
        blank=True, 
        null=True,
        help_text="Description of the tolerance"
        )
    created_at = models.DateTimeField(auto_now_add=True,
        help_text="Date and time when the tolerance was created"
        )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date and time when the tolerance was last updated"
        )
    created_by = models.CharField(max_length=50, 
        blank=True, 
        help_text="User who created the tolerance"
        )
    updated_by = models.CharField(
        max_length=50,
        blank=True, help_text="User who last updated the tolerance"
        )
    
    objects = ISOManager()
    
    class Meta:
        db_table = "tbl_isotolerances_it"
        ordering = ['nominal_size_min', 'tolerance_class']
        verbose_name = "DIN ISO 286-1 IT Toleranz"
        verbose_name_plural = "DIN ISO 286-1 IT Toleranzen"
        unique_together = [['nominal_size_min', 'nominal_size_max', 'tolerance_class']]
    
    def __str__(self):
        return f"{self.tolerance_class} ({self.nominal_size_min}-{self.nominal_size_max}mm)"
    
class ISOToleranceClass(models.Model):

    standards = models.ForeignKey(
        Standards,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    nominal_size_min = models.FloatField(
            help_text="Untere Nominalgrenze [mm]",
            blank=False,
            null=False
        )
    nominal_size_max = models.FloatField(
            help_text="Obere Nominalgrenze [mm]",
            blank=False,
            null=False
        )
    tolerance_class = models.CharField(
            max_length=6,
            help_text="Toleranzklasse (z.B., 'h', 'CD', 'H', 'ZC' etc.)",
            blank=False,
            null=False
        )
    tolerance_grade = models.CharField(
        max_length=2,
        help_text="Toleranzgrad (z.B., '7' in 'h7' oder 'H7')",
        blank=False,
        null=False
    )
    tolerance_min = models.FloatField(
            help_text="Unteres Grenzabmaß = EI [µm]"
        )
    tolerance_max = models.FloatField(
            help_text="Oberes Grenzabmaß = ES [µm]"
        )
    description = models.TextField(
        blank=True, 
        null=True,
        help_text="Description of the tolerance"
        )
    created_at = models.DateTimeField(auto_now_add=True,
        help_text="Datum und Uhrzeit, wann die Toleranz erstellt wurde"
        )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Datum und Uhrzeit, wann die Toleranz zuletzt aktualisiert wurde"
        )
    created_by = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="Benutzer, der die Toleranz erstellt hat"
        )
    updated_by = models.CharField(
        max_length=50,
        blank=True, 
        help_text="Benutzer, der die Toleranz zuletzt aktualisiert hat"
        )
    
    objects = ISOManager()

    def __str__(self):
        return f"{self.tolerance_class}{self.tolerance_grade} ({self.nominal_size_min}-{self.nominal_size_max} mm)"

    class Meta:
        db_table = 'tbl_isotolerances'
        verbose_name = 'DIN ISO 286-2 Tabelle'
        verbose_name_plural = 'DIN ISO 286-2 Tabellen'
        managed = True
        unique_together = [['nominal_size_min', 'nominal_size_max', 'tolerance_class', 'tolerance_grade']]
        ordering = ['nominal_size_min', 'tolerance_class']
