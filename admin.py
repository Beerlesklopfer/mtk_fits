from django import forms
import numpy as np 
from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.http import HttpResponse
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse
import pandas as pd
from io import BytesIO
from django.db.models import Count
from .models import ISOToleranceITClass, ISOToleranceClass
from .constants import TOLERANCE_CLASSES
from django.utils import timezone
from main.models import Standards
import re

# class ImportExcelForm(forms.Form):
#     excel_file = forms.FileField(label='Excel File')
    
class ImportISOForm(forms.Form):
    excel_file = forms.FileField(
        label='Excel-Datei mit DIN ISO 286 Daten',
        help_text='Bitte laden Sie eine Excel-Datei im .xlsx- oder .csv-Format hoch.',
        label_suffix=['xls', 'xlsx', 'csv']
    )
    overwrite = forms.BooleanField(
        label="Vorhandene Einträge mit gleichem Nennmaßbereich und Toleranzklasse überschreiben",
        required=False,
        initial=False,
        help_text="Vorhandene Einträge mit identischem Nennmaßbereich und Toleranzklasse werden überschrieben"
    )

@admin.register(Standards)
class StandardsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'app_name', 'title', 'category', 'description', 'link')
    search_fields = ('title', 'description')
    
@admin.register(ISOToleranceITClass)
class ISOToleranceITClassAdmin(admin.ModelAdmin):
    list_display = ('__str__',  'nominal_size_min', 'nominal_size_max', 'tolerance_class', 'tolerance_value', 'description')
    list_filter = ('tolerance_class', 'standards')
    search_fields = ('tolerance_class', 'tolerance_value')
    ordering = ('tolerance_class', 'nominal_size_min', 'nominal_size_max')
    actions = ['import_from_excel']
    change_list_template = 'fits/admin/it-tolerances.html'
    required_columns = dict(
            nominal_size_min  = 'Nennmaß min [mm]',
            nominal_size_max  = 'Nennmaß max [mm]',
            tolerance_class   = 'Toleranzklasse',
            tolerance_value   = 'Grenzmaß [µm]',
            description       = 'Beschreibung (optional)',
        )
        
    def changelist_view(self, request, extra_context=None):
        # Tolerance classes for the filter dropdown
        # Tolerance classes for the filter dropdown
        extra_context = extra_context or {}
        extra_context['tolerance_classes'] = TOLERANCE_CLASSES

        # Get selected class from request
        selected_class = request.GET.get('it_class')
        if selected_class:
            extra_context['selected_class'] = selected_class
            # Get complete tolerance objects for the selected class
            # Jetzt korrekter Zugriff auf das Model
            tolerances = ISOToleranceITClass.objects.filter(
                tolerance_class=selected_class
            ).order_by('nominal_size_min')
            extra_context['tolerances'] = tolerances
        
        return super().changelist_view(request, extra_context=extra_context)

    def nominal_size_range(self, obj):
        return f"{obj.nominal_size_min}mm - {obj.nominal_size_max}mm"
    nominal_size_range.short_description = 'Nennmaßbereich'
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else obj.description
    description_short.short_description = 'Beschreibung'

from django.contrib import admin
from django.db.models import Q
from .models import ISOToleranceClass

class NominalSizeFilter(admin.SimpleListFilter):
    """Filter für Nominalweiten-Bereiche bis 3100 mm"""
    title = 'Nominalweite [mm]'
    parameter_name = 'nominal_size'

    def lookups(self, request, model_admin):
        return [
            ('0-3', '0 - 3 mm'),
            ('3-6', '3 - 6 mm'),
            ('6-10', '6 - 10 mm'),
            ('10-18', '10 - 18 mm'),
            ('18-30', '18 - 30 mm'),
            ('30-50', '30 - 50 mm'),
            ('50-80', '50 - 80 mm'),
            ('80-120', '80 - 120 mm'),
            ('120-180', '120 - 180 mm'),
            ('180-250', '180 - 250 mm'),
            ('250-315', '250 - 315 mm'),
            ('315-400', '315 - 400 mm'),
            ('400-500', '400 - 500 mm'),
            ('500-630', '500 - 630 mm'),
            ('630-800', '630 - 800 mm'),
            ('800-1000', '800 - 1000 mm'),
            ('1000-1250', '1000 - 1250 mm'),
            ('1250-1600', '1250 - 1600 mm'),
            ('1600-2000', '1600 - 2000 mm'),
            ('2000-2500', '2000 - 2500 mm'),
            ('2500-3100', '2500 - 3100 mm'),
            ('3100-9999', 'über 3100 mm'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            min_val, max_val = self.value().split('-')
            return queryset.filter(
                nominal_size_min__gte=float(min_val),
                nominal_size_max__lte=float(max_val)
            )
        return queryset

class ToleranceClassFilter(admin.SimpleListFilter):
    """Filter für Passungsarten (Spielpassung, Übermaßpassung, Übergangspassung)"""
    title = 'Passungsart'
    parameter_name = 'passungsart'

    def lookups(self, request, model_admin):
        return [
            ('spiel', 'Spielpassung (H/h)'),
            ('uebermass', 'Übermaßpassung (P/p, S/s)'),
            ('uebergang', 'Übergangspassung (K/k, M/m, N/n)'),
            ('wellen', 'Wellentoleranzen (kleinbuchstaben)'),
            ('bohrungen', 'Bohrungstoleranzen (großbuchstaben)'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'spiel':
            return queryset.filter(Q(tolerance_class__in=['H', 'h']))
        elif self.value() == 'uebermass':
            return queryset.filter(Q(tolerance_class__in=['P', 'p', 'S', 's']))
        elif self.value() == 'uebergang':
            return queryset.filter(Q(tolerance_class__in=['K', 'k', 'M', 'm', 'N', 'n']))
        elif self.value() == 'wellen':
            return queryset.filter(tolerance_class__regex=r'^[a-z]+$')
        elif self.value() == 'bohrungen':
            return queryset.filter(tolerance_class__regex=r'^[A-Z]+$')
        return queryset

@admin.register(ISOToleranceClass)
class ISOToleranceClassAdmin(admin.ModelAdmin):
    change_list_template = 'fits/admin/isotolerances.html'
    actions = ['mark_as_verified', 'delete_duplicates']
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'find-duplicates/',
                self.admin_site.admin_view(self.find_duplicates_view),
                name='isotolerance_find_duplicates',
            ),
            path(
                'duplicates-report/',
                self.admin_site.admin_view(self.duplicates_report_view),
                name='isotolerance_duplicates_report',
            ),
        ]
        return custom_urls + urls
    
    list_display = [
        'tolerance_display',
        'nominal_range_display', 
        'tolerance_range_display',
        'tolerance_deviation',
        'created_at',
        'updated_at'
    ]
    
    list_filter = [
        'tolerance_class',
        'tolerance_deviation', 
        NominalSizeFilter,
        ToleranceClassFilter,
        'standards',
        'created_at'
    ]
    
    search_fields = [
        'tolerance_class',
        'tolerance_deviation',
        'description',
        'nominal_size_min',
        'nominal_size_max'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'created_by', 
        'updated_by',
        'duplicate_info'
    ]
        
    fieldsets = (
        ('Grundinformationen', {
            'fields': (
                'standards',
                'tolerance_class', 
                'tolerance_deviation',
                'description'
            )
        }),
        ('Nominalmaße', {
            'fields': (
                ('nominal_size_min', 'nominal_size_max'),
            )
        }),
        ('Toleranzen', {
            'fields': (
                ('tolerance_min', 'tolerance_max'),
            ),
            'description': 'Toleranzen in µm'
        }),
        ('Duplikat-Info', {
            'fields': ('duplicate_info',),
            'classes': ('collapse',),
            'description': 'Informationen über mögliche Duplikate'
        }),
        ('Metadaten', {
            'fields': (
                ('created_at', 'updated_at'),
                ('created_by', 'updated_by')
            ),
            'classes': ('collapse',)
        }),
    )

    def find_duplicates_view(self, request):
        """View für die Duplikatsuche"""
        duplicates = self.find_duplicates()
        
        context = {
            'title': 'Duplikatsuche - ISO Toleranzen',
            'duplicates': duplicates,
            'total_duplicates': sum(len(items) for items in duplicates.values()),
            'opts': self.model._meta,
        }
        return render(request, 'fits/admin/duplicates_report.html', context)
    
    def duplicates_report_view(self, request):
        """View für detaillierten Duplikat-Report"""
        duplicates = self.find_detailed_duplicates()
        
        context = {
            'title': 'Detaillierter Duplikat-Report',
            'duplicates': duplicates,
            'opts': self.model._meta,
        }
        return render(request, 'fits/admin/detailed_duplicates.html', context)
    
    def find_duplicates(self):
        """Finde Duplikate basierend auf den unique_together Feldern"""
        
        # Gruppiere nach den unique_together Feldern
        duplicates = (ISOToleranceClass.objects.values(
            'nominal_size_min', 
            'nominal_size_max', 
            'tolerance_class', 
            'tolerance_deviation'
        ).annotate(
            count=Count('id')
        ).filter(
            count__gt=1
        ).order_by('-count'))
        
        result = {}
        for dup in duplicates:
            key = f"{dup['nominal_size_min']}-{dup['nominal_size_max']}mm {dup['tolerance_class']}{dup['tolerance_deviation']}"
            items = ISOToleranceClass.objects.filter(
                nominal_size_min=dup['nominal_size_min'],
                nominal_size_max=dup['nominal_size_max'],
                tolerance_class=dup['tolerance_class'],
                tolerance_deviation=dup['tolerance_deviation']
            )
            result[key] = items
        
        return result
    
    def find_detailed_duplicates(self):
        """Detaillierte Duplikatsuche mit verschiedenen Kriterien"""
        results = {}
        
        # 1. Exakte Duplikate (alle Felder gleich)
        exact_dupes = (ISOToleranceClass.objects.values(
            'nominal_size_min', 'nominal_size_max', 'tolerance_class', 
            'tolerance_deviation', 'tolerance_min', 'tolerance_max'
        ).annotate(count=Count('id')).filter(count__gt=1))
        
        results['exact_duplicates'] = {
            'description': 'Exakte Duplikate (alle Felder identisch)',
            'data': exact_dupes,
            'count': len(exact_dupes)
        }
        
        # 2. Duplikate mit gleichen Toleranzen aber unterschiedlichen Beschreibungen
        tolerance_dupes = (ISOToleranceClass.objects.values(
            'nominal_size_min', 'nominal_size_max', 'tolerance_class', 
            'tolerance_deviation', 'tolerance_min', 'tolerance_max'
        ).annotate(
            count=Count('id'),
            desc_count=Count('description', distinct=True)
        ).filter(count__gt=1, desc_count__gt=1))
        
        results['tolerance_duplicates'] = {
            'description': 'Duplikate mit unterschiedlichen Beschreibungen',
            'data': tolerance_dupes,
            'count': len(tolerance_dupes)
        }
        
        # 3. Potentielle Duplikate (gleiche Größe und Toleranzklasse)
        potential_dupes = (ISOToleranceClass.objects.values(
            'nominal_size_min', 'nominal_size_max', 'tolerance_class', 'tolerance_deviation'
        ).annotate(count=Count('id')).filter(count__gt=1))
        
        results['potential_duplicates'] = {
            'description': 'Potentielle Duplikate (gleiche Größe und Toleranzklasse)',
            'data': potential_dupes,
            'count': len(potential_dupes)
        }
        
        return results
    
    def is_duplicate_flag(self, obj):
        """Zeige an ob ein Eintrag ein Duplikat ist"""
        duplicates = self.find_duplicates()
        for key, items in duplicates.items():
            if obj in items:
                return '✅ Duplikat'
        return '❌ Eindeutig'
    is_duplicate_flag.short_description = 'Duplikat Status'
    
    def duplicate_info(self, obj):
        """Zeige Duplikat-Informationen im Edit-Formular"""
        duplicates = self.find_duplicates()
        duplicate_groups = []
        
        for key, items in duplicates.items():
            if obj in items:
                duplicate_groups.append(key)
        
        if duplicate_groups:
            html = '<div style="background: #fff3cd; padding: 10px; border: 1px solid #ffeaa7; border-radius: 4px;">'
            html += '<strong>⚠️ Dieser Eintrag ist ein Duplikat:</strong><br>'
            for group in duplicate_groups:
                html += f'• {group}<br>'
            html += '</div>'
            return html
        else:
            return '<span style="color: green;">✅ Dieser Eintrag ist eindeutig</span>'
    duplicate_info.allow_tags = True
    duplicate_info.short_description = 'Duplikat Information'
    
    def mark_as_verified(self, request, queryset):
        """Action zum Markieren von Einträgen als verifiziert"""
        updated = queryset.update(description=models.F('description') + " [VERIFIED]")
        self.message_user(
            request, 
            f'{updated} Einträge wurden als verifiziert markiert.', 
            messages.SUCCESS
        )
    mark_as_verified.short_description = "Markiere ausgewählte Einträge als verifiziert"
    
    def delete_duplicates(self, request, queryset):
        """Action zum Löschen von Duplikaten"""
        # Hier könnte eine Logik zum intelligenten Löschen von Duplikaten implementiert werden
        # Zum Beispiel: Behalte den ältesten Eintrag, lösche die anderen
        
        count = 0
        for obj in queryset:
            # Einfache Implementierung - in der Praxis würde man hier intelligenter vorgehen
            obj.delete()
            count += 1
            
        self.message_user(
            request, 
            f'{count} Einträge wurden gelöscht.', 
            messages.SUCCESS
        )
    delete_duplicates.short_description = "Lösche ausgewählte Duplikate"


    def tolerance_display(self, obj):
        return f"{obj.tolerance_class}{obj.tolerance_deviation}"
    tolerance_display.short_description = 'Toleranz'
    tolerance_display.admin_order_field = 'tolerance_class'
    
    def nominal_range_display(self, obj):
        return f"{obj.nominal_size_min} - {obj.nominal_size_max} mm"
    nominal_range_display.short_description = 'Nominalbereich [mm]'
    nominal_range_display.admin_order_field = 'nominal_size_min'
    
    def tolerance_range_display(self, obj):
        return f"{obj.tolerance_min} - {obj.tolerance_max} µm"
    tolerance_range_display.short_description = 'Toleranzbereich [µm]'
    tolerance_range_display.admin_order_field = 'tolerance_min'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user.username
        obj.updated_by = request.user.username
        super().save_model(request, obj, form, change)
    
    list_per_page = 100  # Mehr Einträge für große Tabellen
    ordering = ['nominal_size_min', 'tolerance_class', 'tolerance_deviation']
    show_facets = admin.ShowFacets.ALWAYS

"""
@admin.register(ISOToleranceClass)
class ISOToleranceClassAdmin(admin.ModelAdmin):
    list_display = ('__str__',  'tolerance_min', 'tolerance_max', 'description')
    list_filter = ('tolerance_class',)
    search_fields = ('tolerance_class', 'tolerance_min', 'tolerance_max')
    ordering = ('tolerance_class', 'tolerance_min', 'tolerance_max')    
    list_display_links = ('__str__',)
    list_per_page = 50
    list_editable = ('tolerance_min', 'tolerance_max')
    list_select_related = True
    actions = ['import_from_excel']
    add_form = ImportISOForm
    change_list_template = 'fits/admin/isotolerances.html'
    required_columns = dict(
            nominal_size_min  = 'Nennmaß min [mm]',
            nominal_size_max  = 'Nennmaß max [mm]',
            tolerance_class   = 'Toleranzklasse',
            tolerance_max     = 'Oberes Grenzmaß [µm]',
            tolerance_min     = 'Unteres Grenzmaß [µm]',
            description       = 'Beschreibung (optional)',
        )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Apply filters from URL parameters
        nominal_size_min = request.GET.get('nominal_size_min')
        nominal_size_max = request.GET.get('nominal_size_max')
        tolerance_class = request.GET.get('tolerance_class')
        
        if nominal_size_min:
            qs = qs.filter(nominal_size_min__gte=nominal_size_min)
        if nominal_size_max:
            qs = qs.filter(nominal_size_max__lte=nominal_size_max)
        if tolerance_class:
            qs = qs.filter(tolerance_class=tolerance_class)
            
        return qs

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Get unique tolerance classes for filter dropdown
        extra_context['tolerance_classes'] = ISOToleranceClass.objects.values_list(
            'tolerance_class', flat=True
        ).distinct().order_by('tolerance_class')
        
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('pastebin/', self.admin_site.admin_view(self.purge_data), name='purge-data'),
            path('import-iso/', self.admin_site.admin_view(self.import_from_excel), name='import-excel'),
            path('export-template/', self.admin_site.admin_view(self.export_to_excel), name='export-to-excel'),
        ]
        return custom_urls + urls

    def import_from_excel(self, request):

        if request.method == 'POST':
            form = ImportISOForm(request.POST, request.FILES)
            
            if form.is_valid():
                try:
                    # Read Excel file into DataFrame
                    if request.FILES['excel_file'].name.endswith('.csv'):
                        df = pd.read_csv(request.FILES['excel_file'])
                    else:
                        df = pd.read_excel(request.FILES['excel_file'])
                        # Check for missing columns
                        missing_cols = [col for col in self.required_columns.keys() if col not in df.columns]

                        if missing_cols:
                            raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")

                    
                    # Clean and validate data
                    # Fill missing values in 'tolerance_class' and 'Description' with whitespace
                    df['tolerance_class'] = df['tolerance_class'].fillna(' ')
                    df['description'] = df['description'].fillna(' ')
                    df = df.replace({np.nan: None})
                    # Keep only required columns
                    df = df[list(self.required_columns.keys())]  
                    
                    # Validate array lengths consistency
                    row_counts = df.count()
                    if len(set(row_counts)) != 1:
                        raise ValueError("All data columns must have the same number of rows")
                    
                    created_count = 0
                    updated_count = 0
                    errors = []
                    
                    for index, row in df.iterrows():
                        try:
                            # Convert data types and validate
                            data = {
                                'nominal_size_min': int(row.get('nominal_size_min')),
                                'nominal_size_max': int(row.get('nominal_size_max')),
                                'tolerance_class': str(row.get('tolerance_class')).strip(),
                                'tolerance_deviation': str(row.get('tolerance_deviation')).strip(),
                                'tolerance_max': float(row.get('tolerance_max')),
                                'tolerance_min': float(row.get('tolerance_min')),
                                'description': str(row.get('description', '')).strip()
                            }

                            # Validate nominal values
                            if data['tolerance_min'] >= data['tolerance_max']:
                                print (f"Nominal size min: {data['nominal_size_min']}, Nominal size max: {data['nominal_size_max']}")
                                raise ValueError(f"{data['tolerance_class']}: Nennmaß max ({data['nominal_size_max']}) muss kleiner als Nennmaß min ({data['nominal_size_min']}) sein")

                            #Validate nominal size range
                            if data['nominal_size_min'] < 0 or data['nominal_size_max'] > 31500:
                                raise ValueError(f"{data['tolerance_class']}: Nennmaß min ({data['nominal_size_min']}) muss >= 0 und max darf nicht größer als 31500 mm ({data['nominal_size_max']}) sein")

                            # Validate fundamental deviation
                            # if not (data['tolerance_class'].isalpha() and len(data['tolerance_class']) > 6 and data['tolerance_class'].isspace()):
                            #     print(data['tolerance_class'])
                            #     raise ValueError("Column 'Tolerance class' must not be a single character or a single whitespace")

                            if data['description']:
                                if data['description'][0].isupper():
                                    data['description'] = 'BOHRUNG' + data['description']
                                else:
                                    data['description'] = 'WELLE' + data['description']

                            # Validate tolerance class format
                            if not re.match(r'^[a-zA-Z]{1,2}\d{0,2}$', data['tolerance_class']):
                                raise ValueError(f"Spalte 'Toleranzklasse' {data['tolerance_class']} muss mit 1-2 Buchstaben (a-z oder A-Z) beginnen, optional gefolgt von bis zu 2 Ziffern")

                            if form.cleaned_data['overwrite']:
                                obj, created = ISOToleranceClass.objects.update_or_create(
                                    nominal_size_min=data['nominal_size_min'],
                                    nominal_size_max=data['nominal_size_max'],
                                    tolerance_class=data['tolerance_class'],
                                    tolerance_max=data['tolerance_max'],
                                    tolerance_min=data['tolerance_min'],
                                    defaults={
                                        'description': data['description'],
                                        'created_at' : timezone.now(),
                                        'updated_at' : timezone.now(),  
                                        'created_by' : request.user.username,
                                        'updated_by' : request.user.username,
                                        }
                                )
                            else:
                                obj, created = ISOToleranceClass.objects.get_or_create(
                                    nominal_size_min=data['nominal_size_min'],
                                    nominal_size_max=data['nominal_size_max'],
                                    tolerance_class=data['tolerance_class'],
                                    tolerance_max=data['tolerance_max'],
                                    tolerance_min=data['tolerance_min'],
                                    defaults={
                                        'description': data['description'],
                                        'created_at' : timezone.now(),
                                        'updated_at' : timezone.now(),  
                                        'created_by' : request.user.username,
                                        'updated_by' : request.user.username,
                                        }
                                )
                            
                            if created:
                                created_count += 1
                            else:
                                updated_count += 1
                                
                        except Exception as e:
                            errors.append(f"Row {index + 2}: {str(e)}")
                            print(f"Error processing row {index + 2}: {str(e)}")
                            continue
                    
                    # Prepare result message
                    msg = f"Successfully processed {created_count + updated_count} rows: "
                    msg += f"{created_count} created" if created_count else ""
                    msg += ", " if created_count and updated_count else ""
                    msg += f"{updated_count} updated" if updated_count else ""
                    messages.success(request, msg)
                    
                    if errors:
                        messages.warning(request, f"{len(errors)} errors occurred during import")
                        for error in errors[:5]:  # Show first 5 errors
                            messages.warning(request, error)
                        if len(errors) > 5:
                            messages.warning(request, f"... and {len(errors) - 5} more errors")
                    
                    return redirect('..')
                
                except Exception as e:
                    messages.error(request, f"Import error: {str(e)}")
        else:
            form = ImportISOForm()

        context = self.admin_site.each_context(request)
        context.update({
            'form': form,
            'opts': self.model._meta,
            'title': 'Import DIN ISO 286 Toleranzendaten',
            'template_columns': dict(self.required_columns),
            'extra_info': {
            'import_type': 'MS Excel',
            'max_rows': 1000,
            'allow_overwrite': True
            }
        })
        return render(request, 'fits/admin/import_iso.html', context)
        
    @classmethod
    def export_to_excel(cls, queryset):
        # Prepare data with consistent array lengths
        data = {
            'nominal_size_min': [],
            'nominal_size_max': [],
            'tolerance_class': [],
            'tolerance_max': [],
            'tolerance_min': [],
            'description': [],
        }


        for tolerance in queryset:
            data['nominal_size_min'].append(tolerance.nominal_size_min)
            data['nominal_size_max'].append(tolerance.nominal_size_max)
            data['tolerance_class'].append(tolerance.tolerance_class)
            data['tolerance_max'].append(tolerance.tolerance_max)
            data['tolerance_min'].append(tolerance.tolerance_min)
            data['description'].append(tolerance.description)

        # Validate array lengths
        array_lengths = [len(v) for v in data.values()]
        if len(set(array_lengths)) != 1:
            raise ValueError("All data arrays must be of the same length for export")
        
        df = pd.DataFrame(data)
        
        # Create Excel response
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='DIN ISO 286 Export')

            # Add documentation sheet
            doc_df = pd.DataFrame({
                'Spalte': list(data.keys()),
                'Beschreibung': [
                    'Untere Grenze des Nennmaßbereichs in mm',
                    'Obere Grenze des Nennmaßbereichs in mm',
                    'Toleranzklasse (z.B. IT6, IT7)',
                    'Oberes Grenzmaß in Mikrometer (µm)',
                    'Unteres Grenzmaß in Mikrometer (µm)',
                    'Beschreibung (optional)'
                ]
            })
            doc_df.to_excel(writer, index=False, sheet_name='Documentation')
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=ISO286_Tolerances_Export.xlsx'
        return response
    
    def purge_data(self, request):
        if request.method == 'POST':
            # Sicherheitsfrage: Bestätigen Sie das Löschen aller Daten
            if not request.POST.get('confirm_purge'):
                messages.error(request, "Bitte bestätigen Sie das Löschen, indem Sie das Kontrollkästchen aktivieren.")
                return redirect(request.path)
            deleted_count, _ = ISOToleranceClass.objects.all().delete()
            messages.success(request, f"All ISO Tolerance Class data has been purged. Deleted {deleted_count} records.")
            return redirect('..')
        
        context = self.admin_site.each_context(request)
        context.update({
            'opts': self.model._meta,
            'title': 'Purge All ISO Tolerance Class Data',
        })
        return render(request, 'fits/admin/purge_confirmation.html', context)
"""    