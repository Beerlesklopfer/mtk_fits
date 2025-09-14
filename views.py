import re
from tkinter import font
from urllib import request
from django.views import View
from django.shortcuts import render, redirect
from django.http import  HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404
from django_htmx.http import trigger_client_event
from .models import ISOToleranceITClass, ISOToleranceClass
from main.models import Standards
from django.db.models import F, IntegerField, FloatField, BooleanField
from django.db.models.functions import Substr, Cast,  StrIndex
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
import logging
import json
import base64
from io import BytesIO
from math import pi, cos, sin
from PIL import Image, ImageDraw, ImageFont
from main.mixins import AppTemplateMixin

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class FitsService:
    """
    Dienst zur Verwaltung und Berechnung von Passungen nach ISO 286.
    Attribute:
    - NominalSize: Nennmaß
    - Bore: Daten für die Bohrung
    - Shaft: Daten für die Welle
    - Tolerance: Toleranzen für die Passung
    - Drawing: Technische Zeichnung im base64-Format

    Methoden:
    - __init__: Initialisiert den FitsService mit den übergebenen Parametern oder Standardwerten.
    - get_tolerancesIT: Gibt die Toleranz-IT-Klassen und -werte für eine angegebene Nennmaß zurück.
    - get_tolerances: Ermittelt und bereitet die Toleranzklassen für Bohrung und Welle basierend auf dem angegebenen Nennmaß vor.
    - get_grades: Gibt die verfügbaren Toleranzgrade für Bohrung oder Welle basierend auf der ausgewählten Toleranzklasse und der Nennmaß zurück.
    - get_values: Gibt die Toleranzwerte für die ausgewählte Toleranzklasse und den ausgewählten Toleranzgrad zurück.
    - get_limit_deviations: Berechnet und setzt die Grenzabmaße für Bohrung und Welle basierend auf Nennmaß, Grundtoleranz und Grenzabmaßen.
    - draw: Erstellt eine technische Zeichnung der Passung basierend auf den aktuellen Bohrungs- und Wellenparametern.    
    """
    # Nennmaß
    NominalSize = float(-1.0)
    
    # Daten für die Bohrung
    Bore = {
        'tolerances' : '',
        'selected_tolerance'  : '',
        'values': {
            'ES': float(-1.0),     #   oberes Grundabmaß
            'EI': float(-1.0),     #   unteres Grundabmaß
        },
        'results': {
            'D': float(-1.0),      #   Durchmesser
            'ES': float(-1.0),     #   oberes Grundabmaß
            'EI': float(-1.0),     #   unteres Grundabmaß
            'IT': float(-1.0),     #   Toleranzgrade
            'T' : float(-1.0),     #   Toleranz T = ES - EI
            'D_max': float(-1.0),  #   maximaler Durchmesser D + ES
            'D_min': float(-1.0),  #   minimaler Durchmesser D - EI
        },
        'grades': [],
        'selected_grade': '',
    }

    # Daten für die Welle
    Shaft = {
        'tolerances': [],
        'selected_tolerance': '',
        'values': {
            'es': float(-1.0),     #   oberes Grundabmaß
            'ei': float(-1.0),     #   unteres Grundabmaß
        },
        'results': {
            'Dd': float(-1.0),     #   Durchmesser
            'es': float(-1.0),     #   oberes Grundabmaß
            'ei': float(-1.0),     #   unteres Grundabmaß
            'it': float(-1.0),     #   Toleranzgrad
            't' : float(-1.0),     #   Toleranz T = ES - EI
            'd_max': float(-1.0),  #   maximaler Durchmesser D + ES
            'd_min': float(-1.0),  #   minimaler Durchmesser D - EI
        },
        'grades': [],
        'selected_grade': '',
    }

    # Toleranzen für die Passung
    Tolerance = {
        # 'tolerances' : request.session.get('fit_Tolerance')['tolerances'] if 'fit_Tolerance' in request.session else [],
        'grades' : [],                # Toleranzklassen für die IT-Klassen
        'values' : [],                # Toleranzwerte für die IT-Klassen
        'selected_tolerance': 0.0,    # ausgewählte Grundtoleranz IT
        'use_iso_286_2': False,       # Wenn True, dann werden die Tabellen aus ISO 286-2 verwendet
        's_min': float(-1.0),         # Mindestspiel
        's_max': float(-1.0),         # Höchstspiel
        'fit-type': 'clearance'       # Passungsart: clearance, transition, interference
    }

    # Platzhalter für die technische Zeichnung im base64-Format
    Drawing = {
        'image': f"data:image/png;base64,{''}",
        'alt': 'Technische Zeichnung',
        'style': {
            'display': 'block',
            'max-width': '100%',
            'height': 'auto',
            'border': '1px solid #dee2e6',
            'border-radius': '4px',
            'box-shadow': '0 2px 4px rgba(0, 0, 0, 0.1)'
        }
    }

    def __init__(self, bore=None, shaft=None, tolerance=None, nominal_size=None):
        """
        Initialisiert den FitsService mit den übergebenen Parametern oder Standardwerten.
        Parameter:
        - bore: Die Bohrungstoleranzen
        - shaft: Die Wellentoleranzen
        - tolerance: Die allgemeinen Toleranzen
        - nominal_size: Die Nennmaßgröße
        """
        self.Bore = bore if bore is not None else self.Bore
        self.Shaft = shaft if shaft is not None else self.Shaft
        self.Tolerance = tolerance if tolerance is not None else self.Tolerance
        self.NominalSize = nominal_size

        if self.NominalSize is None:
            raise ValueError("Nominal size is required")
        elif self.NominalSize < 0:
            raise ValueError("Nominal size must be positive")
        elif self.NominalSize > 31500:
            raise ValueError("Nominal size must be less than or equal to 31500")

    def get_tolerancesIT(self, nominal_size):
        """
        Gibt die Toleranz-IT-Klassen und -werte für eine angegebene Nennmaß zurück.
        Parameter:
            nominal_size (float oder None): Das Nennmaß, für das die Toleranzen abgefragt werden sollen.
                                            Falls None, wird self.NominalSize verwendet.
        Rückgabe:
            dict: Ein Dictionary mit den Schlüsseln 'grades' (Liste der Toleranzklassen) und
                  'values' (Liste der Toleranzwerte) für das angegebene Nennmaß.
        """

        qry_tolerances = ISOToleranceITClass.objects.all(nominal_size or self.NominalSize)
        self.Tolerance['grades'] = list(qry_tolerances.values_list('tolerance_class', flat=True))
        self.Tolerance['values'] = list(qry_tolerances.values_list('tolerance_value', flat=True))
        return self.Tolerance

    def get_tolerances(self, nominal_size=None):
        """
        Ermittelt und bereitet die Toleranzklassen für Bohrung und Welle basierend auf dem angegebenen Nennmaß vor.
        Parameter:
            nominal_size (Optional[float]): Das Nennmaß, für das die Toleranzklassen gesucht werden sollen.
                                            Falls nicht angegeben, wird self.NominalSize verwendet.
        Rückgabe:
            Tuple[dict, dict]: Zwei Dictionaries mit den Toleranzklassen für Bohrung und Welle.
                               Die Toleranzklassen sind als sortierte, duplikatfreie Listen ohne Zahlen enthalten.
        Ausnahme:
            ValueError: Wird ausgelöst, wenn keine Toleranzklassen für das angegebene Nennmaß gefunden werden.
        """
        qry_set = ISOToleranceClass.objects.all(nominal_size or self.NominalSize, isBore=True)
        self.Bore['tolerances'] = list(qry_set.values_list('tolerance_class', flat=True))
        # Entferne alle Zahlen aus den Toleranzklassen
        self.Bore['tolerances'] = [re.sub(r'\d+', '', tol) for tol in self.Bore['tolerances']]        
        self.Bore['tolerances'] = sorted(set(self.Bore['tolerances']))
        if len(self.Bore['tolerances']) == 0:
            raise ValueError(f"Keine Bohrungstoleranzen für Nennmaß {self.NominalSize} mm gefunden")
        
        qry_set = ISOToleranceClass.objects.all(self.NominalSize, isBore=False)

        self.Shaft['tolerances'] = list(qry_set.values_list('tolerance_class', flat=True))
        # Entferne alle Zahlen aus den Toleranzklassen
        self.Shaft['tolerances'] = [re.sub(r'\d+', '', tol) for tol in self.Shaft['tolerances']]
        self.Shaft['tolerances'] = sorted(set(self.Shaft['tolerances']))
        if len(self.Shaft['tolerances']) == 0:
            raise ValueError(f"Keine Wellentoleranzen für Nennmaß {self.NominalSize} mm gefunden")

        return self.Bore, self.Shaft
    
    def get_grades(self, isBore=True):
        """
        Gibt die verfügbaren Toleranzgrade für Bohrung oder Welle basierend auf der ausgewählten Toleranzklasse und der Nennmaß zurück.
        Args:
            isBore (bool, optional): Gibt an, ob die Toleranzgrade für eine Bohrung (True) oder eine Welle (False) abgefragt werden sollen. Standardwert ist True.
        Raises:
            ValueError: Wenn keine Toleranzklasse für Bohrung oder Welle ausgewählt wurde.
            ValueError: Wenn keine Toleranzgrade für die angegebene Nennmaß und Toleranzklasse gefunden wurden.
        Returns:
            list: Eine sortierte Liste der verfügbaren Toleranzgrade (nur Buchstaben) für die ausgewählte Bohrung oder Welle.
        """

        # if isBore:
        #     print(f"\033[93mSELECTED: {self.Bore.items()}\033[0m")
        # else:
        #     print(f"\033[96mSELECTED: {self.Shaft.get('selected_tolerance')}\033[0m")

        tolerance_class = ''
        if isBore:
            if self.Bore.get('selected_tolerance') is None or self.Bore.get('selected_tolerance') == '':
                raise ValueError("No bore tolerance selected")
            tolerance_class=self.Bore['selected_tolerance']
        else:
            if self.Shaft.get('selected_tolerance') is None or self.Shaft.get('selected_tolerance') == '':
                raise ValueError("No shaft tolerance selected")
            tolerance_class=self.Shaft['selected_tolerance']  
        result = ISOToleranceClass.objects.get_grades(
            nominal_size=self.NominalSize,
            tolerance=tolerance_class,
            isBore=isBore
            )
        if len(result) == 0:    
            raise ValueError(f"No {'bore' if isBore else 'shaft'} grades found for nominal size {self.NominalSize} mm and tolerance class {tolerance_class}")
        if isBore:
            self.Bore['grades'] = result
            return self.Bore['grades']
        else:
            self.Shaft['grades'] = result
            return self.Shaft['grades']

    def get_values(self, isBore=True):
        """
        Gibt die Toleranzwerte für die ausgewählte Toleranzklasse und den ausgewählten Toleranzgrad zurück.
        Args:
            isBore (bool, optional): Gibt an, ob die Toleranzwerte für eine Bohrung (True) oder eine Welle (False) abgefragt werden sollen. Standardwert ist True.
        Raises:
            ValueError: Wenn keine Toleranzklasse für Bohrung oder Welle ausgewählt wurde.
            ValueError: Wenn kein Toleranzgrad für die angegebene Nennmaß, Toleranzklasse und Toleranzgrad gefunden wurde.
        Returns:
            dict: Ein Dictionary mit den Schlüsseln 'tolerance_min' und 'tolerance_max', die die entsprechenden Toleranzwerte enthalten.
        """

        # if isBore:
        #     print(f"\033[93mSELECTED: {self.Bore.get('selected_tolerance')} {self.Bore.get('selected_grade')}\033[0m")
        # else:
        #     print(f"\033[96mSELECTED: {self.Shaft.get('selected_tolerance')} {self.Shaft.get('selected_grade')}\033[0m")

        tolerance_class = ''
        tolerance_grade = ''
        if isBore:
            if self.Bore.get('selected_tolerance') is None or self.Bore.get('selected_tolerance') == '':
                raise ValueError("No bore tolerance selected")
            tolerance_class=self.Bore['selected_tolerance']
            if self.Bore.get('selected_grade') is None or self.Bore.get('selected_grade') == '':
                raise ValueError("No bore grade selected")
            tolerance_grade=self.Bore['selected_grade']
        else:
            if self.Shaft.get('selected_tolerance') is None or self.Shaft.get('selected_tolerance') == '':
                raise ValueError("No shaft tolerance selected")
            tolerance_class=self.Shaft['selected_tolerance']  
            if self.Shaft.get('selected_grade') is None or self.Shaft.get('selected_grade') == '':
                raise ValueError("No shaft grade selected")
            tolerance_grade=self.Shaft['selected_grade']  
        
        result = ISOToleranceClass.objects.get_value(
            nominal_size=self.NominalSize,
            tolerance_class=tolerance_class,
            tolerance_grade=tolerance_grade
            )
        if len(result) == 0:    
            raise ValueError(f"No {'bore' if isBore else 'shaft'} values found for nominal size {self.NominalSize} mm, tolerance class {tolerance_class} and grade {tolerance_grade}")
        
        if isBore:
            self.Bore['values']['ES'] = result['tolerance_min'] if result['tolerance_min'] is not None else -1.0
            self.Bore['values']['EI'] = result['tolerance_max'] if result['tolerance_max'] is not None else -1.0
            return self.Bore['values']      
        else:
            self.Shaft['values']['es'] = result['tolerance_min'] if result['tolerance_min'] is not None else -1.0
            self.Shaft['values']['ei'] = result['tolerance_max'] if result['tolerance_max'] is not None else -1.0
            return self.Shaft['values']
    
    def get_limit_deviations(self):
        """
        Berechnet und setzt die Grenzabmaße für Bohrung und Welle basierend auf Nennmaß, Grundtoleranz und Grenzabmaßen.
        Für die Bohrung werden folgende Werte berechnet:
        - ES: Oberes Grenzabmaß der Bohrung
        - EI: Unteres Grenzabmaß der Bohrung
        Für die Welle werden folgende Werte berechnet:
        - es: Oberes Grenzabmaß der Welle
        - ei: Unteres Grenzabmaß der Welle
        Falls erforderliche Werte nicht vorhanden sind, werden die Ergebnisse mit -1.0 als fehlerhaft gesetzt.
        Rückgabe:
            None bei erfolgreichen Prüfungen,
            String mit Fehlermeldung bei Fehlern.
        """
        def get_tolerance_value():
            try:
                self.Tolerance['s_min'] = float(self.Bore['results']['EI'] - self.Shaft['results']['es'])
                self.Tolerance['s_max'] = float(self.Bore['results']['ES'] - self.Shaft['results']['ei'])
                self.Tolerance['fit-type'] = 'clearance' if self.Tolerance['s_min'] > 0 else 'interference' if self.Tolerance['s_max'] < 0 else 'transition'
            except Exception as e:
                logger.error(f"Error retrieving tolerance value: {e}")
                return (1010, f"Error retrieving tolerance value: {e}")

        # Wenn kein Nennmaß gesetzt wurde, dann beende mit Fehlermeldung
        if self.NominalSize is None or self.NominalSize <= 0:
            logger.error("Kein oder falsches Nennmaß vorhanden.")
            return (1004, "Kein oder falsches Nennmaß vorhanden.")

        # Wenn keine Grundtoleranz gewählt wurde, Verwende die Tabellen aus ISO 286-2
        if self.Tolerance.get('use_iso_286_2', True) :
            self.Bore['results']['EI'] = self.Bore['values']['EI'] if self.Bore['values']['EI'] is not None else -1.0
            self.Bore['results']['ES'] = self.Bore['values']['ES'] if self.Bore['values']['ES'] is not None else -1.0
            self.Shaft['results']['ei'] = self.Shaft['values']['ei'] if self.Shaft['values']['ei'] is not None else -1.0
            self.Shaft['results']['es'] = self.Shaft['values']['es'] if self.Shaft['values']['es'] is not None else -1.0
            get_tolerance_value()
            return None

        # Wenn keine Toleranzklasse für Bohrung gewählt wurde, dann beende mit Fehlermeldung
        if self.Bore.get('selected_tolerance', None) is None or self.Bore.get('selected_tolerance', '') == '' \
        or self.Bore.get('selected_grade', None) is None or self.Bore.get('selected_grade', '') == '':
            logger.error("Keine Toleranzklasse für Bohrung gewählt.")
            return (1002, "Keine Toleranzklasse für Bohrung gewählt. Bitte wählen Sie ein Toleranzklasse.")

        match self.Bore['selected_tolerance']:
            case letter if letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'CD', 'EF', 'FG', ]:
                self.Bore['results']['ES'] = self.Bore['values']['EI'] + float(self.Tolerance.get('selected_tolerance'))
            case 'H':
                self.Bore['results']['ES'] = float(self.Tolerance.get('selected_tolerance'))
                self.Bore['results']['EI'] = 0
            case 'JS':
                self.Bore['results']['EI'] = -float(self.Tolerance.get('selected_tolerance')) / 2.0
                self.Bore['results']['ES'] = float(self.Tolerance.get('selected_tolerance')) / 2.0
            case 'J':
                self.Bore['results']['EI'] = None
                self.Bore['results']['ES'] = None
            case 'K' | 'M' | 'N':
                self.Bore['results']['EI'] = None
                self.Bore['results']['ES'] = None
            case letter if letter in ['P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'ZA', 'ZB', 'ZC']:
                self.Bore['results']['EI'] = None
                self.Bore['results']['ES'] = None
            case _:
                self.Bore['results']['EI'] = None
                self.Bore['results']['ES'] = None
                return (1004, "Keine Toleranzklasse für Bohrung gewählt. Bitte wählen Sie ein Toleranzklasse.")

        # Wenn keine Toleranzklasse für Welle gewählt wurde, dann beende mit Fehlermeldung
        if self.Shaft.get('selected_tolerance', None) is None or self.Shaft.get('selected_tolerance', '') == '' \
        or self.Shaft.get('selected_grade', None) is None or self.Shaft.get('selected_grade', '') == '':
            logger.error("Keine Toleranzklasse für Welle gewählt.")
            return (1005, "Keine Toleranzklasse für Welle gewählt. Bitte wählen Sie ein Toleranzklasse.")

        # Convert selected_tolerance to lowercase for consistent matching
        selected_tolerance_lower = self.Bore['selected_tolerance'].lower() if self.Bore.get('selected_tolerance') else ''

        match selected_tolerance_lower:
            case letter if letter in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'cd', 'ef', 'fg']:
                self.Shaft['results']['es'] = self.Shaft['values']['ei'] + float(self.Tolerance.get('selected_tolerance'))
            case 'h':
                self.Shaft['results']['es'] = 0
                self.Shaft['results']['ei'] = -1.0*float(self.Tolerance.get('selected_tolerance'))
            case 'js':
                self.Shaft['results']['ei'] = -float(self.Tolerance.get('selected_tolerance')) / 2.0
                self.Shaft['results']['es'] = float(self.Tolerance.get('selected_tolerance')) / 2.0
            case 'j' | 'k' | 'm' | 'n':
                self.Shaft['results']['ei'] = None
                self.Shaft['results']['es'] = None
            case letter if letter in ['p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'za', 'zb', 'zc']:
                self.Shaft['results']['ei'] = None
                self.Shaft['results']['es'] = None
            case _:
                self.Shaft['results']['ei'] = None
                self.Shaft['results']['es'] = None
                logger.error("Keine Toleranzklasse für Welle gewählt.")
                return (1006, "Keine Toleranzklasse für Welle gewählt. Bitte wählen Sie ein Toleranzklasse.")

        # Zuletzt die Toleranzberechnung durchführen
        get_tolerance_value()
        return None
    
    def draw(self):    
        """
        Erstellt eine technische Zeichnung der Passung basierend auf den aktuellen Bohrungs- und Wellenparametern.
        Die Zeichnung wird als PNG-Bild im base64-Format mit dem post "data:image/png;base64," Präfix zurückgegeben.
        Die Zeichnung zeigt die Bohrung und die Welle mit ihren jeweiligen Grenzabmaßen.
        Ausnahme:
            ValueError: Wenn die erforderlichen Bohrungs- oder Wellenparameter nicht gesetzt wurden.
        Rückgabe:
            str: Ein base64-kodiertes PNG-Bild der technischen Zeichnung mit dem Präfix "data:image/png;base64," 
            oder None, wenn ein Fehler aufgetreten ist.
        """

        # Bild erstellen
        width, height = 1000, 700
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)

        # Schriftart laden
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            font_bold = ImageFont.truetype("arialbd.ttf", 16)
            font_title = ImageFont.truetype("arialbd.ttf", 20)
        except:
            font = ImageFont.load_default()
            font_bold = ImageFont.load_default()
            font_title = ImageFont.load_default()

        # Zeichnungstitel
        title = f"ISO 286 Toleranzdarstellung - {self.Bore.get('selected_tolerance', '')}{self.Bore.get('selected_grade', '')}/{self.Shaft.get('selected_tolerance', '')}{self.Shaft.get('selected_grade', '')}"
        draw.text((width // 2, 30), title, fill='black', font=font_title, anchor='mm')

        # Bohrung und Welle zeichnen
        bore_diameter = self.Bore['results'].get('D', 50)
        shaft_diameter = self.Shaft['results'].get('d', 50)
    
        # Maßstabsfaktor
        scale = 5
        center_x = width // 2
        center_y = height // 2
                
        # Bohrung zeichnen (innen)
        bore_radius = bore_diameter * scale / 2
        bore_x = center_x - bore_radius
        bore_y = center_y - bore_radius
        bore_size = bore_radius * 2
        draw.ellipse([bore_x, bore_y, bore_x + bore_size, bore_y + bore_size], 
                outline='blue', width=3)

        # Welle zeichnen (außen)
        shaft_radius = shaft_diameter * scale / 2
        shaft_x = center_x - shaft_radius
        shaft_y = center_y - shaft_radius
        shaft_size = shaft_radius * 2
        draw.ellipse([shaft_x, shaft_y, shaft_x + shaft_size, shaft_y + shaft_size], 
                outline='red', width=3)
        
        # Toleranzbereiche visualisieren
        bore_max_radius = self.Bore['results'].get('D_max', bore_diameter) * scale / 2
        bore_min_radius = self.Bore['results'].get('D_min', bore_diameter) * scale / 2

        shaft_max_radius = self.Shaft['results'].get('d_max', shaft_diameter) * scale / 2
        shaft_min_radius = self.Shaft['results'].get('d_min', shaft_diameter) * scale / 2

        # Toleranzzonen zeichnen (gestrichelt)
        def draw_dashed_circle(x, y, radius, color, width=2):
            dash_length = 8
            for angle in range(0, 360, 10):
                if angle % 20 < 10:  # Gestrichelt zeichnen
                    rad_angle = angle * pi / 180
                    x1 = x + radius * cos(rad_angle)
                    y1 = y + radius * sin(rad_angle)
                    x2 = x + radius * cos(rad_angle + 0.17)  # Kleiner Winkel für Liniensegment
                    y2 = y + radius * sin(rad_angle + 0.17)
                    draw.line([x1, y1, x2, y2], fill=color, width=width)
        # Bohrungstoleranz
        draw_dashed_circle(center_x, center_y, bore_max_radius, 'lightblue', 2)
        draw_dashed_circle(center_x, center_y, bore_min_radius, 'lightblue', 2)
    
        # Wellentoleranz
        draw_dashed_circle(center_x, center_y, shaft_max_radius, 'pink', 2)
        draw_dashed_circle(center_x, center_y, shaft_min_radius, 'pink', 2)

        # Maßlinien und Beschriftungen
        # Bohrungsmaße
        draw.line([center_x - bore_radius - 50, center_y, center_x - bore_radius - 30, center_y], fill='black', width=1)
        draw.line([center_x + bore_radius + 30, center_y, center_x + bore_radius + 50, center_y], fill='black', width=1)
        draw.line([center_x - bore_radius - 40, center_y - 10, center_x - bore_radius - 40, center_y + 10], fill='black', width=1)
        draw.line([center_x + bore_radius + 40, center_y - 10, center_x + bore_radius + 40, center_y + 10], fill='black', width=1)

        # Wellenmaße
        draw.line([center_x - shaft_radius - 80, center_y, center_x - shaft_radius - 60, center_y], fill='black', width=1)
        draw.line([center_x + shaft_radius + 60, center_y, center_x + shaft_radius + 80, center_y], fill='black', width=1)
        draw.line([center_x - shaft_radius - 70, center_y - 10, center_x - shaft_radius - 70, center_y + 10], fill='black', width=1)
        draw.line([center_x + shaft_radius + 70, center_y - 10, center_x + shaft_radius + 70, center_y + 10], fill='black', width=1)

        # Beschriftungen
        bore_label = f"Bohrung: Ø{bore_diameter} {self.Bore.get('selected_tolerance', '')}"
        shaft_label = f"Welle: Ø{shaft_diameter} {self.Shaft.get('selected_tolerance', '')}"
        tolerance_label = f"Passung: {self.Tolerance.get('fit_type', '')} (Smin: {self.Tolerance.get('s_min', 0):.3f}, Smax: {self.Tolerance.get('s_max', 0):.3f})"

        draw.text((center_x, center_y - bore_radius - 60), bore_label, fill='blue', font=font_bold, anchor='mm')
        draw.text((center_x, center_y - shaft_radius - 90), shaft_label, fill='red', font=font_bold, anchor='mm')
        draw.text((center_x, center_y + bore_radius + 60), tolerance_label, fill='green', font=font_bold, anchor='mm')

        # Toleranzwerte
        bore_tol_text = f"ES: {self.Bore['results'].get('ES', 0):.3f} | EI: {self.Bore['results'].get('EI', 0):.3f} | T: {self.Bore['results'].get('T', 0):.3f}"
        shaft_tol_text = f"es: {self.Shaft['results'].get('es', 0):.3f} | ei: {self.Shaft['results'].get('ei', 0):.3f} | t: {self.Shaft['results'].get('t', 0):.3f}"

        draw.text((center_x, center_y - bore_radius - 40), bore_tol_text, fill='blue', font=font, anchor='mm')
        draw.text((center_x, center_y - shaft_radius - 70), shaft_tol_text, fill='red', font=font, anchor='mm')

        # Legende
        legend_y = height - 120
        draw.rectangle([50, legend_y, 70, legend_y + 15], outline='blue', width=2)
        draw.text((80, legend_y + 7), "Bohrung Nennmaß", fill='black', font=font, anchor='lm')
        
        draw.rectangle([250, legend_y, 270, legend_y + 15], outline='red', width=2)
        draw.text((280, legend_y + 7), "Welle Nennmaß", fill='black', font=font, anchor='lm')
        
        draw_dashed_circle(450, legend_y + 7, 8, 'lightblue', 2)
        draw.text((470, legend_y + 7), "Bohrung Toleranzzone", fill='black', font=font, anchor='lm')
        
        draw_dashed_circle(650, legend_y, 8, 'pink', 2)
        draw.text((670, legend_y + 7), "Welle Toleranzzone", fill='black', font=font, anchor='lm')

        # In Base64 konvertieren
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        self.Drawing['image'] = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}",

        if self.Tolerance.get('iso_286_2', True):
            self.Drawing['alt'] = f"Technische Zeichnung der Passung {self.Bore.get('selected_tolerance', '')}{self.Bore.get('selected_grade', '')}/{self.Shaft.get('selected_tolerance', '')}{self.Shaft.get('selected_grade', '')} für Nennmaß {self.NominalSize} mm"
        else:
            self.Drawing['alt'] = f"Technische Zeichnung der Passung {self.Bore.get('selected_tolerance', '')}/{self.Shaft.get('selected_tolerance', '')} für Nennmaß {self.NominalSize} mm mit Grundtoleranz IT{self.Tolerance.get('selected_tolerance', 0)}"

        if self.Drawing['image'] == '':
            logger.error("Fehler beim Erstellen der technischen Zeichnung")
            return (2006, "Fehler beim Erstellen der technischen Zeichnung")
        return None

    def calculate(self):
        """
        Berechnet und setzt verschiedene Passungswerte für Bohrung und Welle basierend auf der Nennmaß, Toleranz und Grenzabmaßen.
        Für die Bohrung werden folgende Werte berechnet:
        - D: Nennmaß der Bohrung
        - IT: Toleranzwert der Bohrung
        - T: Toleranzfeld (ES - EI)
        - D_min: Mindestmaß der Bohrung (Nennmaß + EI/1000)
        - D_max: Höchstmaß der Bohrung (Nennmaß + ES/1000)
        Für die Welle werden folgende Werte berechnet:
        - it: Toleranzwert der Welle
        - t: Toleranzfeld (es + ei)
        - d_min: Mindestmaß der Welle (Nennmaß + es/1000)
        - d_max: Höchstmaß der Welle (Nennmaß - ei/1000)
        Falls erforderliche Werte nicht vorhanden sind, werden die Ergebnisse auf -1.0 gesetzt.
        """
        response = self.get_limit_deviations()
        if response is not None:
            self.Bore['results'] = {key: -1.0 for key in self.Bore['results']}
            self.Shaft['results'] = {key: -1.0 for key in self.Shaft['results']}
            logger.error(f"Fehler bei der Berechnung der Grenzabmaße: {response}")
            return response
        
        self.Bore['results']['T'] = self.Bore['results']['ES'] - self.Bore['results']['EI']
        self.Bore['results']['D'] = self.NominalSize
        self.Bore['results']['IT'] = float(self.Tolerance.get('selected_tolerance', 0))
        self.Bore['results']['D_min'] = round(float(self.NominalSize + self.Bore['results']['EI']/1000.0), 4)
        self.Bore['results']['D_max'] = round(float(self.NominalSize + self.Bore['results']['ES']/1000.0), 4)

        self.Shaft['results']['t'] = self.Shaft['results']['es'] + self.Shaft['results']['ei']
        self.Shaft['results']['Dd'] = self.NominalSize
        self.Shaft['results']['it'] = float(self.Tolerance.get('selected_tolerance', 0))

        if self.draw() is not None:
            drawing_result = self.draw()
            logger.error(f"Fehler Zeichnung: {drawing_result[:40]}")
            return drawing_result
        
        return None

class FitsView(AppTemplateMixin, TemplateView):

    """View für die Anzeige der FITS-Seite mit den verfügbaren Standards.
    Diese View rendert die Seite mit den FITS-Standards und stellt die notwendigen Kontextdaten bereit.
    
    Attribute:
        template_name (str): Der Name des Templates, das für die Darstellung verwendet wird.
        
    Methoden:
        get_context_data(**kwargs): Überschreibt die Methode zur Bereitstellung zusätzlicher Kontextdaten für das Template."""

    template_name = "fits/index.html"
    app_name = 'fits'

    def get_context_data(self, **kwargs):

        logger.error(f"FITS View: {self.get_app_name()} ")
        standards = Standards.objects.filter(app_name='fits').order_by('title') \
            .values('id', 'title', 'description', 'link')

        context = super().get_context_data(**kwargs)
        context['app_name'] = self.app_name
        context['standards'] = standards
        return context

class FitsRPCView(AppTemplateMixin, View):

    """View für die Verwaltung und Speicherung des FitsService-Objekts in der Benutzersitzung.
    Diese View stellt Methoden zum Abrufen, Speichern und Serialisieren des FitsService-Objekts bereit.

    Attribute:
        template_name (str): Der Name des Templates, das für die Darstellung verwendet wird.
    
    Methoden:
        __init__(**kwargs): Initialisiert die View und stellt sicher, dass das zugehörige Template gesetzt ist.
        get_service(request): Holt die 'fits_service'-Daten aus der Benutzersitzung und rekonstruiert ein FitsService-Objekt.
        save_service(request, service): Speichert die Eigenschaften des übergebenen Service-Objekts in der Session des Requests.
        serialize_service(hint=None): Serialisiert das Service-Objekt und gibt eine JSON-Antwort zurück.
        post_hint(request, hint): Sendet einen Hinweis (Hint) als Antwort aus einer POST-Anfrage.
        post(request): Verarbeitet POST-Anfragen für die FitsService-Ansicht. (DEPRECATED)

    """
    def __init__(self, **kwargs):
        """Initialisiert die View und stellt sicher, dass das zugehörige Template gesetzt ist.
        Versucht, die 'fits_service'-Daten aus der Benutzersitzung zu laden und rekonstruiert ein FitsService-Objekt,
        sofern die Daten vorhanden sind.
        Parameter:
            **kwargs: Zusätzliche Schlüsselwortargumente für die Initialisierung der Basisklasse.
        """
        super().__init__(**kwargs)
        self.template_name = "index.html"

    def get_service(self, request):
        """
        Holt die 'fits_service'-Daten aus der Benutzersitzung und rekonstruiert ein FitsService-Objekt.

        Argumente:
            request: Das HTTP-Request-Objekt mit der Session.

        Rückgabe:
            FitsService: Eine Instanz von FitsService, initialisiert mit den Sitzungsdaten, falls verfügbar.
            None: Falls keine Servicedaten in der Session gefunden werden.
        """
        service_data = request.session.get('fits_service')
        if service_data:
            # Service aus Session wiederherstellen
            service = FitsService(
                bore=service_data.get('Bore'),
                shaft=service_data.get('Shaft'),
                tolerance=service_data.get('Tolerance'),
                nominal_size=service_data.get('NominalSize')
            )
        else:
            service = None
        return service

    def save_service(self, request, service):
        """
        Speichert die Eigenschaften des übergebenen Service-Objekts in der Session des Requests.

        Args:
            request: Das aktuelle HTTP-Request-Objekt.
            service: Ein Objekt, das die Attribute Bore, Shaft, Tolerance und NominalSize enthält.

        Die gespeicherten Werte sind später über 'fits_service' in der Session abrufbar.
        """
        """"""
        request.session['fits_service'] = {
            'Bore': service.Bore,
            'Shaft': service.Shaft,
            'Tolerance': service.Tolerance,
            'NominalSize': service.NominalSize
        }

    def serialize_service(self, hint=None):
        """
        Serialisiert das Service-Objekt und gibt eine JSON-Antwort zurück.
        Diese Methode ruft das Service-Objekt aus der aktuellen Anfrage ab und prüft,
        ob ein Service vorhanden ist. Falls kein Service gefunden wird, wird eine JSON-Antwort
        mit einem Fehler und dem Statuscode 404 zurückgegeben. Andernfalls werden die relevanten
        Attribute des Service-Objekts (Bore, Shaft, Tolerance, NominalSize) in einer erfolgreichen
        JSON-Antwort mit Statuscode 200 zurückgegeben.
        Rückgabe:
            JsonResponse: JSON-Antwort mit den Service-Daten oder einer Fehlermeldung.
        """
        service = self.get_service(self.request)
        if not service:
            return JsonResponse({'success': False, 'error': 'No service found in session'}, status=404)

        # Übermitteln eines Hinweises zusammen mit den Formulardaten
        if hint is not None:
            response = JsonResponse({
                'success': False,
                'messageType': 'Hint',
                'messageIdentifier': hint[0],
                'message': hint[1],
                'data': {
                    'NominalSize': service.NominalSize,
                    'Bore': service.Bore,
                    'Shaft': service.Shaft,
                    'Tolerance': service.Tolerance,
                }
            }, status=200, content_type='application/json', headers={'HX-Trigger': json.dumps({'show-hint': hint[1]})})
            logger.info(f"POST Hint Response: {hint}")
            return response
        else:
            response_data = {
                'success': True,
                'data': {
                    'NominalSize': service.NominalSize,
                    'Bore': service.Bore,
                    'Shaft': service.Shaft,
                    'Tolerance': service.Tolerance,
                    'Drawing': service.Drawing
                }
            }
            return JsonResponse(status=200, content_type='application/json', data=response_data)

    def post_hint(self, request, hint):
        """
        @DEPRECATED
        Sendet einen Hinweis (Hint) als Antwort aus einer POST-Anfrage.
        Args:
            request (HttpRequest): Die eingehende HTTP-POST-Anfrage.
            hint (str): Der zu sendende Hinweis.
        """
        response = JsonResponse({
            'messageType': 'Hint',
            'message': hint
        }, status=200, content_type='application/json', headers={'HX-Trigger': json.dumps({'show-hint': hint})})
        logger.info(f"POST Hint Response: {hint}")
        return response

    def post(self, request):
        """
        Verarbeitet POST-Anfragen für die FitsService-Ansicht.
        Diese Methode verarbeitet die eingehenden Daten entweder als JSON oder als Formulardaten,
        extrahiert relevante Informationen und aktualisiert das Service-Objekt entsprechend.
        Die Methode prüft das Vorhandensein des 'Hx-Trigger'-Headers, um die Art der Aktion zu bestimmen,
        und führt die entsprechende Logik aus (z.B. Aktualisierung der Nennmaß, Toleranz, Bohrung oder Welle).
        Fehlerhafte oder unvollständige Daten werden mit einer entsprechenden Fehlermeldung beantwortet.
        Das aktualisierte Service-Objekt wird in der Session gespeichert und bei Bedarf serialisiert zurückgegeben.
        Args:
            request (HttpRequest): Die eingehende HTTP-POST-Anfrage.
        Returns:
            JsonResponse: Eine JSON-Antwort mit dem Ergebnis der Verarbeitung oder einer Fehlermeldung.
        """

        try:
            if request.content_type == 'application/json':
                form_data = json.loads(request.body.decode('utf-8'))
            else:
                form_data = request.POST.dict()

            form_data['Hx-Trigger'] = request.headers.get('Hx-Trigger') or form_data.get('Hx-Trigger')
            # print("HX-Trigger:", form_data.get('Hx-Trigger')) # Debug-Ausgabe für HX-Trigger

            # Service aus Session holen oder neu erzeugen
            service = self.get_service(request)
            if not service:
                service = FitsService(
                    nominal_size=float(form_data.get('nominal_size', None))
                )

            # Update Service-Objekt mit neuen Werten
            if service.Bore is None:
                service.Bore = {}
                service.Bore['selected_tolerance'] = form_data.get('bore-tolerance', '')
                service.Bore['selected_grade'] = form_data.get('bore-grade', '')
            elif service.Shaft is None:
                service.Shaft = {}
                service.Shaft['selected_tolerance'] = form_data.get('shaft-tolerance', '')
                service.Shaft['selected_grade'] = form_data.get('shaft-grade', '')
            elif service.Tolerance is None:
                service.Tolerance = {}
                service.Tolerance['selected_tolerance'] = form_data.get('tolerance-select', None)
                service.Tolerance['value'] = float(form_data.get('tolerance-value', -1))

            if form_data.get('Hx-Trigger') is None:
                logger.error("Hx-Trigger header is missing in the request")
                raise ValueError("Hx-Trigger is required")

            match request.headers.get('Hx-Trigger'):
                case 'nominal_size':
                    # Remove all leading/trailing non-digit characters around the nominal size
                    raw_nominal_size = form_data.get('nominal_size', '1.0')
                    cleaned_nominal_size = re.sub(r'^\D+|\D+$', '', str(raw_nominal_size))
                    service.NominalSize = float(cleaned_nominal_size or 1.0)
                    service.get_tolerances()
                    service.get_tolerancesIT(nominal_size=service.NominalSize)
                    logger.debug(f"Updated Nominal Size: {service.NominalSize}")
                case 'tolerance-select':
                    service.Tolerance['selected_tolerance'] = form_data.get('tolerance-select', None)
                    service.Bore['IT'] = service.Shaft['it'] = service.Tolerance['value'] = float(form_data.get('tolerance-select', -1))
                    # print(f"\033[90mtolerance-select {float(form_data.get('tolerance-select', -1))}\033[0m")
                case 'bore-tolerance':
                    service.Bore['selected_tolerance'] = form_data.get('bore-tolerance', None)
                    service.get_grades(isBore=True)
                    service.get_values(isBore=True)
                    logger.debug(f"Selected Bore Grade: {service.Bore}")
                case 'shaft-tolerance':
                    service.Shaft['selected_tolerance'] = form_data.get('shaft-tolerance', None)
                    service.get_grades(isBore=False)
                    service.get_values(isBore=False)
                    logger.debug(f"Selected Shaft Grade: {service.Shaft}")
                case 'bore-grade':
                    service.Bore['selected_grade'] = form_data.get('bore-grade', None)
                    service.get_values(isBore=True)
                    logger.debug(f"Selected Bore Grade: {service.Bore}")
                case 'shaft-grade':
                    service.Shaft['selected_grade'] = form_data.get('shaft-grade', None)
                    service.get_values(isBore=False)
                    logger.debug(f"Selected Shaft Grade: {service.Shaft}")
                case 'use_iso_286_2':
                    service.Tolerance['use_iso_286_2'] = form_data.get('use_iso_286_2', 0) == '1'
                    print(f"\033[93mUSE ISO 286-2: {form_data.get('use_iso_286_2', 0)} {service.Tolerance['use_iso_286_2']}\033[0m")
                case _:
                    raise ValueError(f"Unknown Hx-Trigger: {form_data.get('Hx-Trigger')}")


            # Service in Session speichern
            self.save_service(request, service)

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
            return response

        except Exception as e:
            logger.exception(f"\033[91mGeneral POST error occurred: {str(e)} at line {e.__traceback__.tb_lineno}\033[0m")
            response = JsonResponse({
                'messageType': 'GeneralError',
                'message': str(e)
            }, status=400, content_type='application/json', headers={'HX-Trigger': json.dumps({'showError': str(e)})})
            return response

        # Wenn es eine HTMX-Anfrage ist, dann sende die aktualisierten Servicedaten zurück
        result = service.calculate()
        if result is None and request.headers.get('HX-Request') == 'true':
            logger.debug("HTMX Request - returning serialized service")
            return self.serialize_service()
        else:
            logger.error("Non-HTMX Request or calculation error - returning hint or error")
            return self.serialize_service(result or "Unbekannter oder unbehadelter Fehler")

