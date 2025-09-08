import re
from urllib import request
from django.views import View
from django.shortcuts import render, redirect
from django.http import  HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404
from django_htmx.http import trigger_client_event
from .models import ISOTolerance, ISOToleranceClass
from utils.models import Standards
from django.db.models import IntegerField
from django.db.models.functions import Substr, Cast
from django.views.generic import TemplateView
import logging
import json
# from .forms import FitCalculationForm, FitSearchForm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FitsView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        ISOToleranceClass.objects.all()
        ISOTolerance.objects.all()
        standards = Standards.objects.filter(app_name='fits').order_by('title') \
            .values('id', 'title', 'description', 'link')

        context = super().get_context_data(**kwargs)
        context['standards'] = standards

        context = {
            'app_title': 'Passungen',
            'namespace': 'fits',
            'standards': standards
        }

        return context

class FitsRPCView(View):

    tolerances = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # def get(self, request):
    #     response = ''   
    #     if request.headers.get('HX-Request') == 'true':
    #         if request.headers.get('Hx-Target') == 'calculation':
    #             return render(request, 'partials/calculation.html')
    #         elif request.headers.get('Hx-Target') == 'standards':
    #             return render(request, 'partials/standards.html')
    #         elif request.headers.get('Hx-Target') == 'hints':                
    #             return render(request, 'partials/hints.html')
    #         elif request.headers.get('Hx-Target') == 'exercises':
    #             return render(request, 'partials/exercises.html')
    #         elif request.headers.get('Hx-Target') == 'examples':
    #             return render(request, 'partials/examples.html')

    #     return render(request, 'partials/calculation.html')

    def post(self, request):

        ISOToleranceClass.objects.all()  # Ensure the model is loaded
        ISOTolerance.objects.all()

        # Handle the form submission
        try:
            if request.content_type == 'application/json':
                form_data = json.loads(request.body.decode('utf-8'))
                # Extract HX-Trigger from headers or form data
            else:
                form_data = request.POST.dict()

            form_data['Hx-Trigger'] = request.headers.get('Hx-Trigger') or form_data.get('Hx-Trigger')
            self.tolerances = request.session.get('fit_tolerances', {})

            # print("\033[92m", "Form Data:", self.tolerances, "\033[0m")  # green

            Hole = {
                'tolerances' : request.session.get('fit_Hole')['tolerances'] if 'fit_Hole' in request.session else ['A', 'B'],
                'tolerance'  : form_data.get('hole-tolerance', None),
                'values': {
                    'D': float(-1.0),      #   Durchmesser
                    'ES': float(-1.0),     #   oberes Grundabmaß
                    'EI': float(-1.0),     #   unteres Grundabmaß
                    'IT': float(-1.0),     #   Toleranzfeld
                    'I' : float(-1.0),     #   IT-Größe
                    'T' : float(-1.0),     #   Toleranz T = ES - EI
                    'D_max': float(-1.0),  #   maximaler Durchmesser D + ES
                    'D_min': float(-1.0),  #   minimaler Durchmesser D - EI
                },
                'grades': request.session.get('fit_Hole')['grades'] if 'fit_Hole' in request.session else [],
                'grade': form_data.get('hole-grade', None),
            }

            Shaft = {
                'tolerances': request.session.get('fit_Shaft')['tolerances'] if 'fit_Shaft' in request.session else [],
                'tolerance': form_data.get('shaft-tolerance', None),
                'values': {
                    'Dd': float(-1.0),     #   Durchmesser
                    'es': float(-1.0),     #   oberes Grundabmaß
                    'ei': float(-1.0),     #   unteres Grundabmaß
                    'it': float(-1.0),     #   Toleranzfeld
                    'i' : float(-1.0),     #   IT-Größe
                    't' : float(-1.0),     #   Toleranz T = ES - EI
                    'd_max': float(-1.0),  #   maximaler Durchmesser D + ES
                    'd_min': float(-1.0),  #   minimaler Durchmesser D - EI
                },
                'grades': request.session.get('fit_Shaft')['grades'] if 'fit_Shaft' in request.session else [],
                'grade': form_data.get('shaft-grade', None),
            }

            request.session['fit_Hole']  = Hole
            request.session['fit_Shaft']  = Shaft
            request.session['fit_nominal_size'] = float(form_data.get('nominal_size', None))    
            nominal_size = float(form_data.get('nominal_size', 0))

            if nominal_size is None:
                raise ValueError("Nominal size is required")
            elif nominal_size < 0:
                raise ValueError("Nominal size must be positive")
            elif nominal_size > 31500:
                raise ValueError("Nominal size must be less than or equal to 31500")

            if form_data.get('Hx-Trigger') is None:
                raise ValueError("Hx-Trigger is required")

            # Hole zunächst alle Werte über alle Klassen, die einer Nominalspanne liegen
            if form_data.get('Hx-Trigger') == 'nominal_size':
                lst_tolerances = ISOToleranceClass.objects.filter(
                    nominal_size_min__lte=nominal_size,  # Inklusiv
                    nominal_size_max__gt=nominal_size,
                ).values_list('tolerance_class', flat=True).distinct()
                lst_tolerances = list(lst_tolerances)

                # Fetch initial data from model
                if len(lst_tolerances) > 0:
                # Iteriere über alle gefundenen Nennmaße mit großem Anfangsbuchstaben
                    for tolerance in lst_tolerances:
                        # Hole alle Werte über alle Klassen, die der Nominalspanne liegen
                        match = re.match(r'([A-Za-z]+)(\d+)', tolerance)
                        if not match:
                            continue
                        tolerance, grade = match.groups()
                        grade = int(grade)

                        # Groß-/Kleinschreibung entscheiden
                        if tolerance.isupper():
                            Hole['tolerances'].append(tolerance)
                            Hole['grades'].append(grade)
                        else:
                            Shaft['tolerances'].append(tolerance)
                            Shaft['grades'].append(grade)

                # deduplicated Shaft.tolerances and Shaft.grades
                request.session['fit_Hole']['tolerances']  = sorted(list(set(Hole['tolerances'])))
                request.session['fit_Hole']['grades']       = sorted(list(set(Hole['grades'])))
                # same as above: unify it via set and then sort it
                request.session['fit_Shaft']['tolerances']  = sorted(list(set(Shaft['tolerances'])))
                request.session['fit_Shaft']['grades']       = sorted(list(set(Shaft['grades'])))

                lst_tolerances = ISOTolerance.objects.annotate(
                   it_num=Cast(Substr("tolerance_class", 3), IntegerField())
                    ).filter(
                    nominal_size_min__lte=nominal_size,  # Inklusiv
                    nominal_size_max__gt=nominal_size,
                ).values('tolerance_class', 'tolerance_value').order_by('tolerance_value').distinct()
                self.tolerances = list(lst_tolerances)
                request.session['fit_tolerances'] = self.tolerances

                request.session.modified = True

            # Alle passenden Bohrungs-Grade für die ausgewählte Bohrungstoleranz abrufen
            elif request.headers.get('Hx-Trigger') == 'hole-tolerance' \
                and Hole.get('tolerance') is not None:
                lst_holes = ISOToleranceClass.objects.filter(
                    nominal_size_min__lte=nominal_size,
                    nominal_size_max__gt=nominal_size,
                    tolerance_class__regex=r"^" + Hole.get('tolerance').upper()+ r"\d+$"
                )
                lst_holes = list(lst_holes)
                Hole['grades'] = []
                if len(lst_holes) > 0:
                    for hole in lst_holes:
                        match = re.match(r'^\D*(\d+)', hole.tolerance_class)
                        if not match:
                            continue
                        Hole['grades'].append(int(match.group(1)))
                    Hole['grades'] = sorted(set(Hole['grades']))    
                else:
                    Hole['grades'] = []

            # Alle passenden Wellen-Grade für die ausgewählte Wellentoleranz abrufen
            elif request.headers.get('Hx-Trigger') == 'shaft-tolerance' \
                and Shaft.get('tolerance') is not None:
                shaft_list = ISOToleranceClass.objects.filter(
                    nominal_size_min__lte=nominal_size,
                    nominal_size_max__gt=nominal_size,
                    tolerance_class__regex=r"^" + Shaft.get('tolerance').upper()+ r"\d+$"
                )
                shaft_list = list(shaft_list)
                Shaft['grades'] = []
                if len(shaft_list) > 0:
                    for shaft in shaft_list:
                        match = re.match(r'^\D*(\d+)', shaft.tolerance_class)
                        if not match:
                            continue
                        Shaft['grades'].append(int(match.group(1)))
                    Shaft['grades'] = sorted(set(Shaft['grades']))    
                else:
                    Shaft['grades'] = []

            # Alle passenden Wellen-Grade für die ausgewählte Wellentoleranz abrufen
            # Rufe die Toleranzwerte der Bohrung ab
            if Hole.get('tolerance') is not None \
                and Hole.get('grade') is not None:
                lst_holes = ISOToleranceClass.objects.filter(
                    nominal_size_min__lte=nominal_size,
                    nominal_size_max__gt=nominal_size,
                    tolerance_class= \
                        f"{Hole.get('tolerance')}{Hole.get('grade')}"
                ).values('tolerance_min', 'tolerance_max')
                if lst_holes.exists():
                    Hole['values']['ES'] = int(lst_holes.first()['tolerance_max'])
                    Hole['values']['EI'] = int(lst_holes.first()['tolerance_min'])
                    # request.session.save()

            # Rufe die Toleranzwerte der Welle ab
            if form_data.get('shaft-tolerance', None) is not None \
                and form_data.get('shaft-grade', None) is not None:
                shaft_list = ISOToleranceClass.objects.filter(
                    nominal_size_min__lte=nominal_size,
                    nominal_size_max__gt=nominal_size,
                    tolerance_class= \
                        f"{form_data.get('shaft-tolerance', '')}{form_data.get('shaft-grade', '')}"
                ).values('tolerance_min', 'tolerance_max')
                print("Aktualisierte Toleranzwerte:", shaft_list)
                if shaft_list.exists():
                    Shaft['values']['es'] = int(shaft_list.first().get('tolerance_max'))
                    Shaft['values']['ei'] = int(shaft_list.first().get('tolerance_min'))
                    print("Aktualisierte Toleranzwerte:", Shaft['values'])

            # Hole['values']['K']     = float(form_data.get('tolerance-select'))
            k = float(form_data.get('tolerance-value', 18.56144638549669))

            # Hole['values']['ES'] = float(30)
            # Hole['values']['EI'] = float(0)

            # Shaft['values']['es'] = float(0)
            # Shaft['values']['ei'] = float(50)

            Hole['values']['D']     = nominal_size
            Hole['values']['I']     = float((0.45 * (nominal_size ** (1/3)) + 0.001 * nominal_size))
            # Hole['values']['IT']    = float(Hole['values']['I'] * k
            Hole['values']['T']     = float(Hole['values']['ES'] - Hole['values']['EI'])
            Hole['values']['D_min'] = round(float(nominal_size + Hole['values']['EI']/1000.0), 4)
            Hole['values']['D_max'] = round(float(nominal_size + Hole['values']['ES']/1000.0), 4)

            Shaft['values']['i']     = float((0.45 * (nominal_size ** (1/3)) + 0.001 * nominal_size))
            Shaft['values']['it']    = float(Shaft['values']['i'] * k)
            Shaft['values']['t']     = float(Shaft['values']['es'] + Shaft['values']['ei'])
            Shaft['values']['d_min'] = round(float(nominal_size + Shaft['values']['es']/1000.0), 4)
            Shaft['values']['d_max'] = round(float(nominal_size - Shaft['values']['ei']/1000.0), 4)

            # finally store session value
            request.session.modified = True

        except ValueError as ve:
            logger.exception(f"\033[91mValue error occurred: {str(ve)} at line {ve.__traceback__.tb_lineno}\033[0m")
            response = JsonResponse({
                'messageType': 'ValueError',
                    'message': str(ve),
            }, 
            status=400, 
            content_type='application/json', 
            headers={'HX-Trigger': json.dumps({'showError': str(ve)})}
            )
            # ValueError exception end
            return response

        except Exception as e:
            logger.exception(f"\033[91mGeneral POST error occurred: {str(e)} at line {e.__traceback__.tb_lineno}\033[0m")
            response = JsonResponse({
                'messageType': 'GeneralError',
                'message': str(e)
            }, status=400, content_type='application/json', headers={'HX-Trigger': json.dumps({'showError': str(e)})})
            # GeneralException end
            return response


        print("\033[93m", "Hole Data:", Hole['values'], "\033[0m")   # yellow
        print("\033[94m", "Shaft Data:", Shaft['values'], "\033[0m") # blue
        # übermittle werte an den Browser
        if request.headers.get('HX-Request') == 'true':
            return JsonResponse({
                'success': True, 
                'message': 'Form submitted successfully',
                'data': {
                    'nominal_size': nominal_size,
                    'Tolerances': self.tolerances,
                    'Hole': Hole,
                    'Shaft': Shaft,
                }
            })
            
            
        return JsonResponse({'success': False, 'error': 'Invalid POST request'}, status=404)