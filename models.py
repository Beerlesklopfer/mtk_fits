from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext as _
from utils.models import Standards 

# this class represents ISO286 tolerances table
# @deprecated use ISOToleranceClass instead
class ISOTolerance(models.Model):
    TOLERANCE_CLASSES = [
        ('IT1', 'IT1'), ('IT2', 'IT2'),
        ('IT3', 'IT3'), ('IT4', 'IT4'),
        ('IT5', 'IT5'), ('IT6', 'IT6'),
        ('IT7', 'IT7'), ('IT8', 'IT8'),
        ('IT9', 'IT9'), ('IT10', 'IT10'),
        ('IT11', 'IT11'), ('IT12', 'IT12'),
        ('IT13', 'IT13'), ('IT14', 'IT14'),
        ('IT15', 'IT15'), ('IT16', 'IT16'),
        ('IT17', 'IT17'), ('IT18', 'IT18'),
    ]
    
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
    
    class Meta:
        db_table = "tbl_isotolerances_it"
        verbose_name = "ISO286 Tolerance"
        ordering = ['nominal_size_min', 'tolerance_class']
        verbose_name_plural = "ISO286 Tolerances"
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
            help_text="Untere Nominalgrenze [mm]"
        )
    nominal_size_max = models.FloatField(
            help_text="Obere Nominalgrenze [mm]"
        )
    tolerance_class = models.CharField(
            max_length=6,
            help_text="Toleranzklasse (z.B., 'IT0', 'IT00', 'IT1', 'IT3')"
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

    def __str__(self):
        return f"{self.tolerance_class} ({self.nominal_size_min}-{self.nominal_size_max} mm)"

    class Meta:
        db_table = 'tbl_isotolerances'
        managed = True
        unique_together = [['nominal_size_min', 'nominal_size_max', 'tolerance_class']]
        ordering = ['nominal_size_min', 'tolerance_class']
        verbose_name = 'Toleranz Klasse'
        verbose_name_plural = 'Toleranz Klassen'