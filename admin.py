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
    change_list_template = 'admin/ittolerances.html'
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
    change_list_template = 'admin/isotolerances.html'
    required_columns = dict(
            nominal_size_min  = 'Nennmaß min [mm]',
            nominal_size_max  = 'Nennmaß max [mm]',
            tolerance_class   = 'Toleranzklasse',
            tolerance_max     = 'Oberes Grenzmaß [µm]',
            tolerance_min     = 'Unteres Grenzmaß [µm]',
            description       = 'Beschreibung (optional)',
        )
        # def get(self, request, *args, **kwargs):
        #     """
        #     Handles GET requests for the admin view.
        #     """
        #     context = self.admin_site.each_context(request)
        #     context.update({
        #         'opts': self.model._meta,
        #         'title': 'ISO Tolerance Classes',
        #         'template_columns': ISOToleranceClass.objects.all(),
        #     })
        #     return render(request, 'admin/isotolerances.html', context)

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
                                'tolerance_grade': str(row.get('tolerance_grade')).strip(),
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
        return render(request, 'admin/import_iso.html', context)
        
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
        return render(request, 'admin/purge_confirmation.html', context)