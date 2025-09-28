import re
from tkinter import font
from urllib import request
from django.views import View
from django.shortcuts import render, redirect
from django.http import  HttpResponse, JsonResponse, FileResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404
from django_htmx.http import trigger_client_event
from sqlalchemy import case
from .models import ISOToleranceITClass, ISOToleranceClass
from django.conf import settings    
from main.models import Standards
from django.db.models import F, IntegerField, FloatField, BooleanField
from django.db.models.functions import Substr, Cast,  StrIndex
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
import logging, json, base64
from io import BytesIO
from math import pi, cos, sin
from PIL import Image, ImageDraw, ImageFont
from main.mixins import AppTemplateMixin
from django.conf import settings
from math import sin, radians

if  getattr(settings, 'DEBUG', True):
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

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
    - get_deviations: Gibt die verfügbaren Toleranzgrade für Bohrung oder Welle basierend auf der ausgewählten Toleranzklasse und der Nennmaß zurück.
    - get_values: Gibt die Toleranzwerte für die ausgewählte Toleranzklasse und den ausgewählten Toleranzgrad zurück.
    - get_limit_deviations: Berechnet und setzt die Grenzabmaße für Bohrung und Welle basierend auf Nennmaß, Grundtoleranz und Grenzabmaßen.
    - draw_image: Erstellt eine technische Zeichnung der Passung basierend auf den aktuellen Bohrungs- und Wellenparametern.    
    """

    # Daten für die Bohrung
    Bore = {
        'nominal_size': float(0.0),  # Nennmaß
        'tolerances' : [],
        'selected_tolerance'  : 'H',
        'values': {
            'ES': float(-1.0),     #   oberes Grundabmaß
            'EI': float(-1.0),     #   unteres Grundabmaß
        },
        'results': {
            'ULS': float(-1.0),     #   oberes Grundabmaß
            'LLS': float(-1.0),     #   unteres Grundabmaß
            'T' : float(-1.0),     #   Toleranz T = ES - EI
        },
        'deviations': [],
        'selected_deviation': '7',
    }

    # Daten für die Welle
    Shaft = {
        'nominal_size': float(0.0),  # Nennmaß
        'tolerances': [],
        'selected_tolerance': 'h',
        'values': {
            'es': float(-1.0),     #   oberes Grundabmaß
            'ei': float(-1.0),     #   unteres Grundabmaß
        },
        'results': {
            'uls': float(-1.0),    #   oberes Grundabmaß
            'lls': float(-1.0),    #   unteres Grundabmaß
            't' : float(-1.0),     #   Toleranz T = ES - EI
        },
        'deviations': [],
        'selected_deviation': '7',
    }

    # Toleranzen für die Passung
    Tolerance = {
        # 'tolerances' : request.session.get('fit_Tolerance')['tolerances'] if 'fit_Tolerance' in request.session else [],
        'nominal_size': float(0.0),   # Nennmaß
        'deviations' : [],            # Toleranzklassen für die IT-Klassen
        'values' : [],                # Toleranzwerte für die IT-Klassen
        'selected_tolerance': 0.0,    # ausgewählte Grundtoleranz IT
        's_min': float(-1.0),         # Mindestspiel
        's_max': float(-1.0),         # Höchstspiel
        'fit-type': '',               # Passungsart: clearance, transition, interference
        'fit_system': 'bore',         # Passungssystem, entweder 'combined', 'hole' oder 'shaft'
    
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

    def __init__(self, bore=None, shaft=None, tolerance=None, drawing=None):
        """
        Initialisiert den FitsService mit den übergebenen Parametern oder Standardwerten.
        Parameter:
        - bore: Die Bohrungstoleranzen
        - shaft: Die Wellentoleranzen
        - tolerance: Die allgemeinen Toleranzen
        - drawing: Die technische Zeichnung im base64-Format
        """
        self.Bore = bore if bore is not None else self.Bore
        self.Shaft = shaft if shaft is not None else self.Shaft
        self.Tolerance = tolerance if tolerance is not None else self.Tolerance
        self.Drawing = drawing if drawing is not None else self.Drawing

        # Validierung des Nennmaßes
        if self.Tolerance.get('nominal_size') is None:
            raise ValueError("Nennmaß ist erforderlich")
        elif float(self.Tolerance.get('nominal_size')) < 0:
            raise ValueError("Nennmaß muss positiv sein")
        elif float(self.Tolerance.get('nominal_size')) > 31500:
            raise ValueError("Nennmaß muss kleiner oder gleich 31500 sein")

    def get_tolerancesIT(self, nominal_size):
        """
        Gibt die Toleranz-IT-Klassen und -werte für eine angegebene Nennmaß zurück.
        Parameter:
            nominal_size (float oder None): Das Nennmaß, für das die Toleranzen abgefragt werden sollen.
                                            Falls None, wird self.Tolerance['nominal_size'] verwendet.
        Rückgabe:
            dict: Ein Dictionary mit den Schlüsseln 'deviations' (Liste der Toleranzklassen) und
                  'values' (Liste der Toleranzwerte) für das angegebene Nennmaß.
        """

        qry_tolerances = ISOToleranceITClass.objects.all(nominal_size or self.Tolerance.get('nominal_size', -1.0))
        self.Tolerance['deviations'] = list(qry_tolerances.values_list('tolerance_class', flat=True))
        self.Tolerance['values'] = list(qry_tolerances.values_list('tolerance_value', flat=True))
        return self.Tolerance

    def get_tolerances(self, nominal_size=None):
        """
        Ermittelt und bereitet die Toleranzklassen für Bohrung und Welle basierend auf dem angegebenen Nennmaß vor.
        Wenn kein Nennmaß angegeben ist, wird self.Tolerance['nominal_size'] verwendet.

        Parameter:
            nominal_size (Optional[float]): Das Nennmaß, für das die Toleranzklassen gesucht werden sollen.
                                            Falls nicht angegeben, wird self.Tolerance['nominal_size'] verwendet.
        Rückgabe:
            Tuple[dict, dict]: Zwei Dictionaries mit den Toleranzklassen für Bohrung und Welle.
                               Die Toleranzklassen sind als sortierte, duplikatfreie Listen ohne Zahlen enthalten.
        Ausnahme:
            ValueError: Wird ausgelöst, wenn keine Toleranzklassen für das angegebene Nennmaß gefunden werden.
        """

        # wenn kein Wert übergeben wurde, dann verwende den gespeicherten Wert
        self.Tolerance['nominal_size'] = float(nominal_size) if nominal_size is not None else float(self.Tolerance.get('nominal_size', 0.0))
        qry_set = ISOToleranceClass.objects.all(nominal_size or self.Tolerance.get('nominal_size', -1.0), isBore=True)
        self.Bore['tolerances'] = list(qry_set.values_list('tolerance_class', flat=True))
        # Entferne alle Zahlen aus den Toleranzklassen
        self.Bore['tolerances'] = [re.sub(r'\d+', '', tol) for tol in self.Bore['tolerances']]        
        self.Bore['tolerances'] = sorted(set(self.Bore['tolerances']))
        if len(self.Bore['tolerances']) == 0:
            raise ValueError(f"Keine Bohrungstoleranzen für Nennmaß {self.Tolerance['nominal_size']} mm gefunden")

        qry_set = ISOToleranceClass.objects.all(self.Tolerance.get('nominal_size', -1.0), isBore=False)

        self.Shaft['tolerances'] = list(qry_set.values_list('tolerance_class', flat=True))
        # Entferne alle Zahlen aus den Toleranzklassen
        self.Shaft['tolerances'] = [re.sub(r'\d+', '', tol) for tol in self.Shaft['tolerances']]
        self.Shaft['tolerances'] = sorted(set(self.Shaft['tolerances']))
        if len(self.Shaft['tolerances']) == 0:
            raise ValueError(f"Keine Wellentoleranzen für Nennmaß {self.Tolerance['nominal_size']} mm gefunden")

        return self.Bore, self.Shaft

    def get_deviations(self, tolerance_class=None, isBore=True):
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

        print( f"\033[94mDEBUG: Getting bore deviations for nominal size {self.Tolerance.get('nominal_size', -1.0)} mm and tolerance class {self.Bore.get('selected_tolerance', '')}\033[0m")
        if isBore:
            if self.Bore.get('selected_tolerance', tolerance_class if tolerance_class is not None else None) is None or self.Bore.get('selected_tolerance') == '':
                raise ValueError("Keine Bohrungstoleranz ausgewählt (Buchstabe)")
        else:
            if self.Shaft.get('selected_tolerance') is None or self.Shaft.get('selected_tolerance') == '':
                raise ValueError("Keine Wellentoleranz ausgewählt (Buchstabe)")

        # Hole die vorhandenen Toleranzgrade für die ausgewählte Toleranzklasse und Nennmaß 
        result = ISOToleranceClass.objects.get_deviations(
            nominal_size=self.Tolerance.get('nominal_size', -1.0),
            tolerance=self.Bore['selected_tolerance'] if isBore else self.Shaft['selected_tolerance'],
            isBore=isBore
            )
        if len(result) == 0:    
            raise ValueError(f"No {'bore' if isBore else 'shaft'} deviations found for nominal size {self.get('nominal_size', -1.0)} mm and tolerance class {tolerance_class}")
        else:
            # Bohrung
            if isBore:
                self.Bore['deviations'] = result
                return self.Bore['deviations']
            
            # Welle
            else:
                self.Shaft['deviations'] = result
                return self.Shaft['deviations']        
        return None

    def get_values(self, tolerance_class=None, tolerance_deviation=None, isBore=True):
        """
        Gibt die Toleranzwerte für die ausgewählte Toleranzklasse und den ausgewählten Toleranzgrad zurück.
        Args:
            isBore (bool, optional): Gibt an, ob die Toleranzwerte für eine Bohrung (True) oder eine Welle (False) abgefragt werden sollen. Standardwert ist True.
            tolerance_class (str): Die Toleranzklasse, für die die Werte abgefragt werden sollen.
            tolerance_deviation (str): Der Toleranzgrad, für den die Werte abgefragt werden sollen.
        Raises:
            ValueError: Wenn keine Toleranzklasse für Bohrung oder Welle ausgewählt wurde.
            ValueError: Wenn kein Toleranzgrad für die angegebene Nennmaß, Toleranzklasse und Toleranzgrad gefunden wurde.
        Returns:
            dict: Ein Dictionary mit den Schlüsseln 'tolerance_min' und 'tolerance_max', die die entsprechenden Toleranzwerte enthalten.
        """
        
        result = ISOToleranceClass.objects.get_value(
            nominal_size=self.Tolerance.get('nominal_size', -1.0),            
            tolerance_class=tolerance_class,
            tolerance_deviation=tolerance_deviation
            )
        if not isinstance(result, dict) or not result:
            raise ValueError(f"Keine {'Bohrungs' if isBore else 'Wellen'}werte für Nennmaß {self.Tolerance.get('nominal_size', -1.0)} mm, Toleranzklasse {tolerance_class}{tolerance_deviation} gefunden")
        else:
            if isBore:
                self.Bore['values']['ES']    = result['tolerance_min'] if result.get('tolerance_min') is not None else -1.0
                self.Bore['values']['EI']    = result['tolerance_max'] if result.get('tolerance_max') is not None else -1.0
                self.Bore['results']['ES']   = self.Bore['values']['ES']
                self.Bore['results']['EI']   = self.Bore['values']['EI']
                self.Bore['results']['T']    = self.Bore['values']['ES'] + self.Bore['values']['EI']
                self.Bore['results']['ULS']  = round(self.Bore.get('nominal_size') + self.Bore['values']['ES'] / 1000.0, 3)
                self.Bore['results']['LLS']  = round(self.Bore.get('nominal_size') + self.Bore['values']['EI'] / 1000.0, 3)
                # logger.debug(f"\033[94mResult From Database {'bore' if isBore else 'shaft'}  {self.Bore['results']}\033[0m")
                return self.Bore
            else:
                self.Shaft['values']['es']   = result['tolerance_max'] if result.get('tolerance_min') is not None else -1.0
                self.Shaft['values']['ei']   = result['tolerance_min'] if result.get('tolerance_max') is not None else -1.0
                self.Shaft['results']['es']  = self.Shaft['values']['es']
                self.Shaft['results']['ei']  = self.Shaft['values']['ei']
                self.Shaft['results']['t']   = self.Shaft['values']['es'] - self.Shaft['values']['ei']
                self.Shaft['results']['uls'] = round(self.Shaft.get('nominal_size') + self.Shaft['values']['es'] / 1000.0 , 3)
                self.Shaft['results']['lls'] = round(self.Shaft.get('nominal_size') + self.Shaft['values']['ei'] / 1000.0, 3)
                # logger.debug(f"\033[94mResult From Database {'bore' if isBore else 'shaft'}  {self.Shaft['results']}\033[0m")
                return self.Shaft
            
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
        # Wenn kein Nennmaß gesetzt wurde, dann beende mit Fehlermeldung
        if self.Tolerance['nominal_size'] is None or self.Tolerance['nominal_size'] <= 0:
            logger.error("Kein oder falsches Nennmaß vorhanden.")
            raise ValueError("Kein oder falsches Nennmaß vorhanden.")

        # Wenn keine Grundtoleranz gewählt wurde, Verwende die Tabellen aus ISO 286-2
        # self.Bore['results']['EI'] = self.Bore['values']['EI'] if self.Bore['values']['EI'] is not None else -1.0
        # self.Bore['results']['ES'] = self.Bore['values']['ES'] if self.Bore['values']['ES'] is not None else -1.0
        # self.Shaft['results']['ei'] = self.Shaft['values']['ei'] if self.Shaft['values']['ei'] is not None else -1.0
        # self.Shaft['results']['es'] = self.Shaft['values']['es'] if self.Shaft['values']['es'] is not None else -1.0

        # Wenn keine Toleranzklasse für Bohrung gewählt wurde, dann beende mit Fehlermeldung
        # if self.Bore.get('selected_tolerance', None) is None or self.Bore.get('selected_tolerance', '') == '' \
        # or self.Bore.get('selected_deviation', None) is None or self.Bore.get('selected_deviation', '') == '':
        #     logger.error("Keine Toleranzklasse für Bohrung gewählt.")
        #     return (1002, "Keine Toleranzklasse für Bohrung gewählt. Bitte wählen Sie ein Toleranzklasse.")

        # match self.Bore['selected_tolerance']:
        #     case letter if letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'CD', 'EF', 'FG', ]:
        #         self.Bore['results']['ES'] = self.Bore['values']['EI'] + float(self.Tolerance.get('selected_tolerance'))
        #     case 'H':
        #         self.Bore['results']['ES'] = float(self.Tolerance.get('selected_tolerance'))
        #         self.Bore['results']['EI'] = 0
        #     case 'JS':
        #         self.Bore['results']['EI'] = -float(self.Tolerance.get('selected_tolerance')) / 2.0
        #         self.Bore['results']['ES'] = float(self.Tolerance.get('selected_tolerance')) / 2.0
        #     case 'J':
        #         self.Bore['results']['EI'] = None
        #         self.Bore['results']['ES'] = None
        #     case 'K' | 'M' | 'N':
        #         self.Bore['results']['EI'] = None
        #         self.Bore['results']['ES'] = None
        #     case letter if letter in ['P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', 'ZA', 'ZB', 'ZC']:
        #         self.Bore['results']['EI'] = None
        #         self.Bore['results']['ES'] = None
        #     case _:
        #         self.Bore['results']['EI'] = None
        #         self.Bore['results']['ES'] = None
        #         return (1004, "Keine Toleranzklasse für Bohrung gewählt. Bitte wählen Sie ein Toleranzklasse.")

        # Wenn keine Toleranzklasse für Welle gewählt wurde, dann beende mit Fehlermeldung
        if self.Shaft.get('selected_tolerance', None) is None or self.Shaft.get('selected_tolerance', '') == '' \
        or self.Shaft.get('selected_deviation', None) is None or self.Shaft.get('selected_deviation', '') == '':
            logger.error("Keine Toleranzklasse für Welle gewählt.")
            raise ValueError("Keine Toleranzklasse für Welle gewählt. Bitte wählen Sie ein Toleranzklasse.")

        # Convert selected_tolerance to lowercase for consistent matching
        # selected_tolerance_lower = self.Shaft['selected_tolerance'].lower() if self.Bore.get('selected_tolerance') else ''

        # match selected_tolerance_lower:
        #     case letter if letter in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'cd', 'ef', 'fg']:
        #         self.Shaft['results']['es'] = self.Shaft['values']['ei'] + float(self.Tolerance.get('selected_tolerance'))
        #     case 'h':
        #         self.Shaft['results']['es'] = 0
        #         self.Shaft['results']['ei'] = -1.0*float(self.Tolerance.get('selected_tolerance'))
        #     case 'js':
        #         self.Shaft['results']['ei'] = -float(self.Tolerance.get('selected_tolerance')) / 2.0
        #         self.Shaft['results']['es'] = float(self.Tolerance.get('selected_tolerance')) / 2.0
        #     case 'j' | 'k' | 'm' | 'n':
        #         self.Shaft['results']['ei'] = None
        #         self.Shaft['results']['es'] = None
        #     case letter if letter in ['p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', 'za', 'zb', 'zc']:
        #         self.Shaft['results']['ei'] = None
        #         self.Shaft['results']['es'] = None
        #     case _:
        #         self.Shaft['results']['ei'] = None
        #         self.Shaft['results']['es'] = None
        #         logger.error("Keine Toleranzklasse für Welle gewählt.")
        #         raise ValueError("Keine Toleranzklasse für Welle gewählt. Bitte wählen Sie ein Toleranzklasse.")

        # Zuletzt die Toleranzberechnung durchführen
        try:
            self.Tolerance['s_max'] = float(self.Bore['results']['ES'] - self.Shaft['results']['ei'])
            self.Tolerance['s_min'] = float(self.Bore['results']['EI'] - self.Shaft['results']['es'])
            self.Tolerance['fit_type'] = 'clearance' if self.Tolerance['s_min'] > 0 else 'interference' if self.Tolerance['s_max'] < 0 else 'transition'
            # logger.debug(f"\033[94mCalculated fit type: {self.Tolerance['fit_type']} with s_min: {self.Tolerance['s_min']} and s_max: {self.Tolerance['s_max']}\033[0m")
        except Exception as e:
            logger.error(f"Fehler beim Berechnen der Toleranzwerte: {e}")
            raise ValueError(f"Fehler beim Berechnen der Toleranzwerte: {e}")

        return None
    
    def draw_image(self):
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

        def draw_subscript(draw, x, y, text, font_main, font_sub, fill="black", subscript_offset=6):
            """
            Zeichnet Text mit optionalem Tiefstellen von Teilstrings, z.B. "s_min".
            
            - draw: ImageDraw.Draw Objekt
            - x, y: Startkoordinaten für normalen Text
            - text: String, z.B. "s_min" oder "s_max"
            - font_main: Font für normalen Text
            - font_sub: Font für Subscript
            - fill: Farbe
            - subscript_offset: Pixel nach unten für Tiefstellung
            """
            # Prüfen, ob "_" im Text vorhanden ist
            if "_" in text:
                text = text.split(" ")
                # Tupple mit dem Unterstrich trennen
                for i, t in enumerate(text):
                    if "_" in t:
                        main_text, sub_text = t.split("_", 1)
                        # Normale Schrift zeichnen
                        draw.text((x, y), main_text, fill=fill, font=font_main)
                        # Breite und Höhe des normalen Textes ermitteln
                        bbox = font_main.getbbox(main_text)
                        w_main = bbox[2] - bbox[0]
                        h_main = bbox[3] - bbox[1]
                        # Subscript zeichnen, leicht nach unten versetzt
                        draw.text((x + w_main, y + h_main + subscript_offset), text[i], fill=fill, font=font_sub)
                        # x für den nächsten Text anpassen
                        x += w_main + font_sub.getlength(text[i]) + font_main.getlength(" ")
                    else:
                        draw.text((x, y), t, fill=fill, font=font_main)
                        bbox = font_main.getbbox(t)
                        w_t = bbox[2] - bbox[0]
                        x += w_t + font_main.getlength(" ")

        # Bild erstellen
        width, height = 1000, 700
        img = Image.new('RGBA', (width, height), (180, 180, 180, 100))
        draw = ImageDraw.Draw(img)

        # Schriftart laden
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            font_sub = ImageFont.truetype("arialbd.ttf", 10)
            font_y_axis = ImageFont.truetype("arial.ttf", 14)
            font_y_axis.bold = True
            font_y_axis.align = "right"
            font_bold = ImageFont.truetype("arialbd.ttf", 16)
            font_title = ImageFont.truetype("arialbd.ttf", 40)
            nominal_size = self.Tolerance.get('nominal_size', -1.0)

            # Liste relevanter Maße (Nominalmaß + Ergebnisse)
            Dd = {
                "nominal": self.Bore.get('nominal_size'),
                "ULS": self.Bore['results'].get('ULS'),
                "LLS": self.Bore['results'].get('LLS'),
                "uls": self.Shaft['results'].get('uls'),
                "lls": self.Shaft['results'].get('lls')
            }
            logger.debug(f"\033[94mRelevant dimensions for drawing: {Dd}\033[0m")
            # max. Abweichung von Nominalmaß berechnen
            max_dev = max(abs(v - nominal_size) for v in Dd.values() if isinstance(v, (int, float)))
            # Platz oben/unten: 20 %        
            padding = 0.2 * max_dev
            y_min = nominal_size - (max_dev + padding)
            y_max = nominal_size + (max_dev + padding)

            # Wenn liste eine None-Werte enthält, spriunge aus der Funktion
            if any(v is None or v <= 0 for v in Dd.values()):
                logger.error(f"\033[91mBohrungs- oder Wellendurchmesser nicht gesetzt oder ungültig. {Dd}\033[0m")
                # Wenn Werte ungültig sind, gib ein leeres PNG-Bild zurück
                buf = BytesIO()
                empty_img = Image.new('RGB', (10, 10), (255, 255, 255, 0))
                # Schreibe einen Text mit Fehlermeldung ins leere Bild
                error_draw = ImageDraw.Draw(empty_img)
                error_text = "Fehler: Bohrungs- oder Wellendurchmesser nicht gesetzt oder ungültig."
                error_draw.text((2, 2), error_text, fill='red')
                empty_img.save(buf, format='PNG')
                buf.seek(0)
                self.Drawing['image'] = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
                return {base64.b64encode(buf.getvalue()).decode('utf-8')}
                # raise ValueError("Bohrungs- oder Wellendurchmesser nicht gesetzt oder ungültig.")
            
        except:
            font = ImageFont.load_default()
            font_bold = ImageFont.load_default()
            font_title = ImageFont.load_default()

        self.get_limit_deviations()

        # Zeichnungstitel
        title = f"Passung: {self.Bore.get('selected_tolerance', '')}{self.Bore.get('selected_deviation', '')} / {self.Shaft.get('selected_tolerance', '')}{self.Shaft.get('selected_deviation', '')}"
        title += f" - Nennmaß: {self.Tolerance.get('nominal_size', -1.0)} mm"
        draw.text((width // 2, 50), title, fill='black', font=font_title, anchor='mm')

        # Bohrung und Welle zeichnen
        bore_diameter = self.Bore['results'].get('D', 10)
        shaft_diameter = self.Shaft['results'].get('d', 10)
        if bore_diameter <= 0 or shaft_diameter <= 0:
            raise ValueError("Bohrungs- oder Wellendurchmesser nicht gesetzt oder ungültig.")
        
        center_x = int(width // 2)
        center_y = int(height // 2)
        margin_left = int(width * 0.1)
        margin_right = int(width - 10)
        margin_top = int(height * 0.1)
        margin_bottom = int(height - (height * 0.1))
        arrow_size = 8 # Pfeilspitzen für die Achsen

        # Berechne die Höhe des Fonts für die Platzierung des Textes
        fit_min_bbox = draw.textbbox((0, 0), "A", font=font_bold)
        fit_min_height = fit_min_bbox[3] - fit_min_bbox[1] if fit_min_bbox else 20
        fit_min_width = fit_min_bbox[2] - fit_min_bbox[0] if fit_min_bbox else 20
        # Achsenränder
        axis_margin = int(margin_left - 4 * arrow_size)
        
        # Umrechnungsfunktion von mm -> Pixel
        def y_to_px(val):
            ret = int(margin_bottom - (val - y_min) / (y_max - y_min) * (margin_bottom - margin_top))
            # logger.debug(f"y_to_px({val}) =>  -> {ret}")
            return ret

        # Achsen zeichnen
        # Y-Achse (vertikal, links)
        draw.line([(margin_left, margin_top), (margin_left, margin_bottom)], fill='black', width=2)
        draw.line([(margin_left, center_y), (margin_right, center_y)], fill='black', width=2)

        arrow_width = int(sin(radians(30)) * arrow_size )  # Breite der Pfeilspitze basierend auf dem Winkel

        # Pfeilspitze oben
        draw.polygon([
            (margin_left, margin_top),
            (margin_left + arrow_width, margin_top+arrow_size),
            (margin_left - arrow_width, margin_top+arrow_size)
            ], fill='black')
        
        # Pfeilspitze unten
        draw.polygon([
            (margin_left, margin_bottom),
            (margin_left + arrow_width, margin_bottom - arrow_size),
            (margin_left - arrow_width, margin_bottom - arrow_size)
        ], fill='black')

        y_legende = Image.new('RGB', (int(margin_left-arrow_size), height), (242, 242, 242, 0))
        y_draw = ImageDraw.Draw(y_legende)

        # Werte als float-Liste mit 10 gleichmäßig verteilten Schritten zwischen min(Dd) und max(Dd)
        if all(isinstance(v, (int, float)) for v in Dd.values()) and min(Dd.values()) != max(Dd.values()):
            steps = 10
            values = [y_min + i * (y_max - y_min) / steps for i in range(steps + 1)]
            values = [round(v, 3) for v in values]
        else:
            values = [nominal_size]

            # values = sorted(values)

        # Y-Achsen-Beschriftungen zeichnen
        for i, v in enumerate(values):
            if i == 0 or i == len(values) - 1:
                continue 
            y_pos = y_to_px(v)
            draw.line([(margin_left - 5, y_pos), (margin_left, y_pos)], fill="black", width=1)
            draw.text((axis_margin, y_pos), f"{v:.3f}", fill='black', font=font_y_axis, anchor='rm')

        # Bohrung (H7) als grünes Rechteck
        y_top = min(y_to_px(Dd['ULS']), y_to_px(Dd['LLS']))
        y_bottom = max(y_to_px(Dd['ULS']), y_to_px(Dd['LLS']))
        left = margin_left + margin_left/10

        draw.rectangle(
            [(left, margin_top), (left + margin_left*1.5, y_top)],
            outline="green", fill=(144, 238, 144, 50)  # hellgrün transparent
        )
        draw.rectangle(
            [(left, y_top), (left + margin_left*1.5, y_bottom)],
            outline="green", fill=(144, 238, 144, 255)  # hellgrün vollständig sichtbar
        )

        # Welle als blaues Rechteck
        y_top = min(y_to_px(Dd['uls']), y_to_px(Dd['uls']))
        y_bottom = max(y_to_px(Dd['lls']), y_to_px(Dd['lls']))
        left = left + margin_left*1.8
        draw.rectangle(
            [(left, y_bottom), (left + margin_left*1.5, margin_bottom)],
            outline="blue", fill=(144, 238, 244, 50)  # hellblau transparent
        )
        draw.rectangle(
            [(left, y_top), (left + margin_left*1.5, y_bottom)],
            outline="blue", fill=(144, 238, 244, 255)  # hellblau vollständig sichtbar
        )

        # Übergangsbereich s_min als gelbes Rechteck
        y_top = min(y_to_px(Dd['uls']), y_to_px(Dd['ULS']))
        y_bottom = max(y_to_px(Dd['uls']), y_to_px(Dd['ULS']))
        left = left + margin_left*1.8
        draw.rectangle(
            [(left, y_top), (left + margin_left*1.5, y_bottom)],
            outline="yellow", fill=(255, 255, 224, 50)  # hellgelb transparent
        )
        # Draw the ULS value centered above the yellow rectangle
        draw.text(
            # ( (margin_left*1.5 - left) // 2, y_top - fit_min_height * 2),
            ( (left + margin_left*1.5 // 2) , y_top - fit_min_height ),
            f"{Dd['ULS']:.3f} mm",
            fill=(10, 10, 10, 255),
            font=font_bold, anchor='mb'
        )

        # Draw the uls value centered below the yellow rectangle
        draw.text(
            # ( (margin_left*1.5 - left) // 2, y_top - fit_min_height * 2),
            ( (left + margin_left*1.5 // 2) , y_bottom + fit_min_height ),
            f"{Dd['uls']:.3f} mm",
            fill=(10, 10, 10, 255),
            font=font_bold, anchor='mt'
        )

        # Übergangsbereich s_max als oranges Rechteck
        y_top = min(y_to_px(Dd['lls']), y_to_px(Dd['LLS']))
        y_bottom = max(y_to_px(Dd['lls']), y_to_px(Dd['LLS']))
        left = left + margin_left*1.8
        draw.rectangle(
            [(left, y_top), (left + margin_left*1.5, y_bottom)],
            outline="orange", fill=(255, 224, 192, 50)  # hellorange transparent
        )

        # Draw the ULS value centered above the yellow rectangle
        draw.text(
            # ( (margin_left*1.5 - left) // 2, y_top - fit_min_height * 2),
            ( (left + margin_left*1.5 // 2) , y_top - fit_min_height ),
            f"{Dd['LLS']:.3f} mm",
            fill=(10, 10, 10, 255),
            font=font_bold, anchor='mb'
        )

        # Draw the uls value centered below the yellow rectangle
        draw.text(
            # ( (margin_left*1.5 - left) // 2, y_top - fit_min_height * 2),
            ( (left + margin_left*1.5 // 2) , y_bottom + fit_min_height ),
            f"{Dd['lls']:.3f} mm",
            fill=(10, 10, 10, 255),
            font=font_bold, anchor='mt'
        )

        # Legende mit Rechteck rechts unten
        legend_y = margin_bottom - 130
        legend_x = margin_right - 150

        # Legendenrahmen
        draw.rectangle(
            [(legend_x, legend_y), (margin_right, legend_y + 160)],
            outline="black", fill=(255, 255, 255, 200)  # weiß mit Transparenz
        )
        draw.text((legend_x + (margin_right - legend_x) // 2, legend_y + 5), "Legende", fill='black', font=font_bold, anchor='ma')  

        # Bohrung
        legend_y = legend_y + 40
        draw.rectangle(
            [(legend_x + 10, legend_y), (legend_x + 30, legend_y + 20)],
            outline="green", fill=(144, 238, 144, 128)      # hellgrün transparent
        )
        draw.text((legend_x + 40, legend_y), f"Bohrung {self.Bore.get('selected_tolerance', '')}{self.Bore.get('selected_deviation', '')}", fill='black', font=font)

        #Welle
        legend_y = legend_y + 30
        draw.rectangle(
            [(legend_x + 10, legend_y), (legend_x + 30, legend_y + 20)],
            outline="blue", fill=(144, 238, 244, 128)  # hellblau transparent
        )
        draw.text((legend_x + 40, legend_y), f"Welle {self.Shaft.get('selected_tolerance', '')}{self.Shaft.get('selected_deviation', '')}", fill='black', font=font)

        # Passungsbereich Minimales Spiel
        legend_y = legend_y + 30
        draw.rectangle(
            [(legend_x + 10, legend_y), (legend_x + 30, legend_y + 20)],
            outline="yellow", fill=(255, 255, 224, 128)  # hellgelb transparent
        )
        if self.Tolerance.get('fit_type', '') == 'clearance' or self.Tolerance.get('fit_type', '') == 'transition':
            draw.text((legend_x + 40, legend_y), f"Minimales Spiel", fill='black', font=font)
        else:
            draw.text((legend_x + 40, legend_y), f"Maximales Spiel", fill='black', font=font)

        # Passungsbereich Maximales Spiel
        legend_y = legend_y + 30
        draw.rectangle(
            [(legend_x + 10, legend_y), (legend_x + 30, legend_y + 20)],
            outline="orange", fill=(255, 224, 192, 50)  # helles orange transparent
        )
        if self.Tolerance.get('fit_type', '') == 'clearance' or self.Tolerance.get('fit_type', '') == 'transition':
            draw.text((legend_x + 40, legend_y), f"Maximales Spiel", fill='black', font=font)
        else:
            draw.text((legend_x + 40, legend_y), f"Minimales Spiel", fill='black', font=font)

        # Zeichnung speichern
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        # self.Drawing['image'] = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}",

        # if self.Tolerance.get('iso_286_2', True):
        #     self.Drawing['alt'] = f"Technische Zeichnung der Passung {self.Bore.get('selected_tolerance', '')}{self.Bore.get('selected_deviation', '')}/{self.Shaft.get('selected_tolerance', '')}{self.Shaft.get('selected_deviation', '')} für Nennmaß {self.Tolerance['nominal_size']} mm"
        # else:
        #     self.Drawing['alt'] = f"Technische Zeichnung der Passung {self.Bore.get('selected_tolerance', '')}/{self.Shaft.get('selected_tolerance', '')} für Nennmaß {self.Tolerance['nominal_size']} mm mit Grundtoleranz IT{self.Tolerance.get('selected_tolerance', 0)}"

        # if self.Drawing['image'] == '':
        #     logger.error("Fehler beim Erstellen der technischen Zeichnung")
        #     return (2006, "Fehler beim Erstellen der technischen Zeichnung")
        return buf

    def calculate(self):
        """
        Berechnet und setzt verschiedene Passungswerte für Bohrung und Welle basierend auf der Nennmaß, Toleranz und Grenzabmaßen.
        Für die Bohrung werden folgende Werte berechnet:
        - D: Nennmaß der Bohrung
        - T: Toleranzfeld (ES - EI)
        - D_min: Mindestmaß der Bohrung (Nennmaß + EI/1000)
        - D_max: Höchstmaß der Bohrung (Nennmaß + ES/1000)
        Für die Welle werden folgende Werte berechnet:
        - t: Toleranzfeld (es + ei)
        - d_min: Mindestmaß der Welle (Nennmaß + es/1000)
        - d_max: Höchstmaß der Welle (Nennmaß - ei/1000)
        Falls erforderliche Werte nicht vorhanden sind, werden die Ergebnisse auf -1.0 gesetzt.
        """
                
        response = self.get_limit_deviations()
        if response is not None:
            self.Bore['results'] = {key: -1.0 for key in self.Bore['results']}
            self.Shaft['results'] = {key: -1.0 for key in self.Shaft['results']}
        else:
            logger.error(f"Fehler bei der Berechnung der Grenzabmaße: {response}")
            raise ValueError(f"Fehler bei der Berechnung der Grenzabmaße")      
        
        # Mindest- und Höchstmaße der Bohrung berechnen
        try:    
            self.Tolerance['s_min'] = float(self.Bore['results']['EI'] - self.Shaft['results']['es'])
            self.Tolerance['s_max'] = float(self.Bore['results']['ES'] - self.Shaft['results']['ei'])
            self.Tolerance['fit_type'] = 'clearance' if self.Tolerance['s_min'] > 0 else 'interference' if self.Tolerance['s_max'] < 0 else 'transition'
        except Exception as e:
            logger.error(f"Error retrieving tolerance value: {e}")
            return (505, f"Error retrieving tolerance value: {e}")
        
        
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

    template_name = "fits/index.html"
    app_name = 'fits'
    app_description = 'Passungen nach ISO 286-1 und ISO 286-2'
    app_version = '0.1.0'
    app_email = 'joerg@bernau.family'
    app_website = 'https://www.bernau.family'

    def __init__(self, **kwargs):
        """Initialisiert die View und stellt sicher, dass das zugehörige Template gesetzt ist.
        Versucht, die 'fits_service'-Daten aus der Benutzersitzung zu laden und rekonstruiert ein FitsService-Objekt,
        sofern die Daten vorhanden sind.
        Parameter:
            **kwargs: Zusätzliche Schlüsselwortargumente für die Initialisierung der Basisklasse.
        """
        super().__init__(**kwargs)
        if not self.template_name:
            raise ValueError("Template name must be set for FitsRPCView")
        
    def load_session(self, request):
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
                drawing=service_data.get('Drawing')
            )
            # print(f"\033[92mLoaded FitsService from session: {service_data}\033[0m")
        else:
            service = None
        return service

    def save_session(self, request, service):
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
            'Drawing': service.Drawing
        }
        request.session.modified = True
        # print(f"\033[92mSaved FitsService to session: {request.session['fits_service']}\033[0m")

    def serialize_session(self, hint=None):
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
        service = self.load_session(self.request)
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
                    'Bore': service.Bore,
                    'Shaft': service.Shaft,
                    'Tolerance': service.Tolerance,
                    'Drawing': service.Drawing
                }
            }, status=200, content_type='application/json', headers={'HX-Trigger': json.dumps({'show-hint': hint[1]})})
            # logger.info(f"POST Hint Response: {hint}")
            return response
        else:
            response_data = {
                'success': True,
                'data': {
                    'Bore': service.Bore,
                    'Shaft': service.Shaft,
                    'Tolerance': service.Tolerance,
                    'Drawing': service.Drawing
                }
            }
            return JsonResponse(status=200, content_type='application/json', data=response_data)

    def get(self, request):

        service = self.load_session(request)

        context = {}
        context['app_name'] = self.app_name
        context['app_description'] = self.app_description
        context['app_version'] = self.app_version
        context['app_email'] = self.app_email
        context['app_website'] = self.app_website
        context['service'] = service if service else None

        # context['Bore'] = self.load_session(request).Bore if self.load_session(request) else None
        # context['Shaft'] = self.load_session(request).Shaft if self.load_session(request) else None
        template_name = getattr(self, 'template_name', None) or "fits/index.html"
        
        match request.path:
            case '/fits/':
                logger.debug(f"Rendering template: {template_name}")
                return render(request, template_name, context)
            case '/fits/calculation/image/':
                img = service.draw_image()
                if img is not None:
                    return FileResponse(img, content_type='image/png')
            case _:
                return JsonResponse({'error': 'Unknown path'}, status=404)

    def post(self, request, tolerance=None, deviations=None):
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

        # # Kontextdaten initialisieren
        # context = {
        #     'app_name': self.app_name,
        #     'service': None,
        #     'Bore': None,
        #     'Shaft': None,
        #     'Tolerance': None,
        #     'Drawing': None,
        # }

        try:
            if request.content_type == 'application/json':
                form_data = json.loads(request.body.decode('utf-8'))
            else:
                form_data = request.POST.dict()

            form_data['Hx-Trigger'] = request.headers.get('Hx-Trigger') or form_data.get('Hx-Trigger')

            # Service aus Session holen oder neu erzeugen
            service = self.load_session(request)
            if not service:
                service = FitsService(
                    tolerance={
                        'nominal_size': float(form_data.get('nominal_size', 0.0)),
                        'fit-type-msg': '',
                        'fit-type': 'bore',
                        }
                )

            # Update Service-Objekt mit neuen Werten
            # if service.Bore is None:
            #     service.Bore = {}
            #     service.Bore['selected_tolerance'] = form_data.get('bore_tolerance', '')
            #     service.Bore['selected_deviation'] = form_data.get('bore_grade', '')
            # elif service.Shaft is None:
            #     service.Shaft = {}
            #     service.Shaft['selected_tolerance'] = form_data.get('shaft_tolerance', '')
            #     service.Shaft['selected_deviation'] = form_data.get('shaft_grade', '')
            # elif service.Tolerance is None:
            #     service.Tolerance = {}
            #     service.Tolerance['nominal_size'] = float(form_data.get('nominal_size', 1.0))
            #     service.Tolerance['selected_tolerance'] = form_data.get('tolerance-select', None)
            #     service.Tolerance['value'] = float(form_data.get('tolerance-value', -1))
            #     service.Tolerance['fit_type_system_msg'] = form_data.get('fit_type_system_msg', '')
            #     service.Tolerance['fit-type-msg'] = form_data.get('fit-type-msg', '')

            if form_data.get('Hx-Trigger') is None:
                logger.error("Hx-Trigger header is missing in the request")
                raise Exception("Hx-Trigger is required")

            match request.headers.get('Hx-Trigger'):
                case 'nominal_size':
                    # Aktualisiere Nennmaß und berechne Toleranzen
                    nominal = float(form_data.get('nominal_size', 0.0))
                    service.get_tolerances( nominal )
                    service.Tolerance['nominal_size']   = nominal
                    service.Bore['nominal_size']        = nominal
                    service.Bore['selected_tolerance']  = form_data.get('bore_tolerance', 'H')
                    service.Bore['selected_deviation']  = form_data.get('bore_deviation', 7 )
                    service.Shaft['nominal_size']       = nominal
                    service.Shaft['selected_tolerance'] = form_data.get('shaft_tolerance', 'h')
                    service.Shaft['selected_deviation'] = form_data.get('shaft_deviation', 7 )
                    service.get_limit_deviations()
                    # service.calculate()
                    # logger.debug(f"\033[92mAfter Nominal Size update: \nBore: {service.Bore}\n, Shaft:\n{service.Shaft},\nTolerance:\n{service.Tolerance}\033[0m")
                # case 'tolerance-select':
                case 'bore_tolerance':
                    # Setze den Wert auch wenn vom disabled Select Formularfeld nichts zurückkommt
                    service.Bore['selected_tolerance'] = form_data.get('bore_tolerance', 
                        'H' if form_data.get('fit-system-select') == 'bore' and form_data.get('bore_tolerance') is None else None)
                    service.get_deviations(isBore=True)
                    # logger.debug(f"\033[94mAfter Nominal Bore-tolerance update: {service.Bore.get('deviations', [])} {service.Bore['selected_tolerance']}\033[0m" )
                    html = render_to_string("fits/partials/iso286_selects.html", {
                        'values': service.Bore.get('deviations', []),
                        'selected': service.Bore.get('selected_deviation', None)
                    })
                    self.save_session(request, service)
                    return HttpResponse(html)
                case 'bore_deviation':
                    service.Bore['selected_tolerance'] = form_data.get('bore_tolerance', 'H')
                    service.Bore['selected_deviation'] = form_data.get('bore_deviation', 7)

                    service.get_values(isBore=True, tolerance_class=service.Bore.get('selected_tolerance', None), tolerance_deviation=service.Bore.get('selected_deviation', None) )
                    self.save_session(request, service)
                    html = render_to_string("fits/partials/data_section.html", {
                        'fit_system': 'bore',
                        'ES_value':  f"{service.Bore.get('results', {}).get('ES', 0)} µm",
                        'EI_value':  f"{service.Bore.get('results', {}).get('EI', 0)} µm",
                        'T_value':   f"{service.Bore.get('results', {}).get('T', 0)} µm",
                        'ULS_value': f"{service.Bore.get('results', {}).get('ULS', 0):.3f}  mm",
                        'LLS_value': f"{service.Bore.get('results', {}).get('LLS', 0):.3f}  mm"
                    })
                    # logger.debug(f"\033[94mSelected Bore Results: {service.Bore.get('results')}\033[0m")
                    self.save_session(request, service)
                    return HttpResponse(html)
                case 'shaft_tolerance':
                    # Setze den Wert auch wenn vom disabled Select Formularfeld nichts zurückkommt
                    service.Shaft['selected_tolerance'] = form_data.get('shaft_tolerance', 
                        'h' if form_data.get('fit-system-select') == 'shaft' and form_data.get('shaft_tolerance') is None else None)
                    service.get_deviations(isBore=False)
                    # logger.debug(f"\033[94mAfter Nominal Shaft-tolerance update: {service.Shaft.get('deviations', [])} {service.Shaft['selected_tolerance']}\033[0m" )
                    html = render_to_string("fits/partials/iso286_selects.html", {
                        'values': service.Shaft.get('deviations', []),
                        'selected': service.Shaft.get('selected_deviation', None)
                    })
                    self.save_session(request, service)
                    return HttpResponse(html)
                case 'shaft_deviation':
                    service.Shaft['selected_tolerance'] = form_data.get('shaft_tolerance', 'h')
                    service.Shaft['selected_deviation'] = form_data.get('shaft_deviation', 7)

                    service.get_values(isBore=False, tolerance_class=service.Shaft.get('selected_tolerance', None), tolerance_deviation=service.Shaft.get('selected_deviation', None) )
                    html = render_to_string("fits/partials/data_section.html", {
                        'fit_system': 'shaft',
                        'ES_value':  f"{service.Shaft.get('results', {}).get('es', 0)} µm",
                        'EI_value':  f"{service.Shaft.get('results', {}).get('ei', 0)} µm",
                        'T_value':   f"{service.Shaft.get('results', {}).get('t', 0)} µm",
                        'ULS_value': f"{service.Shaft.get('results', {}).get('uls', 0):.3f} mm",
                        'LLS_value': f"{service.Shaft.get('results', {}).get('lls', 0):.3f} mm"
                    })
                    # logger.debug(f"\033[94mSelected Shaft Results: {service.Shaft.get('results')}\033[0m")
                    self.save_session(request, service)
                    return HttpResponse(html)
                case 'fit_system_select':
                    service.Tolerance['fit_system'] = form_data.get('fit_system_select', None)
                    self.save_session(request, service)
                    logger.debug(f"\033[91m: Set fit system to: {service.Tolerance['fit_system']}\033[0m")
                case 's_min':
                    return HttpResponse(service.Tolerance.get('s_min'), status=200)
                case 's_max':
                    return HttpResponse(service.Tolerance.get('s_max'), status=200)
                case 'fit_type':
                    # logger.debug(f"\033[92mDEBUG: Found fit type: {service.Tolerance.get('fit_type')}\033[0m")
                    match service.Tolerance.get('fit_type'):
                        case 'clearance':                    
                            return HttpResponse("Spielpassung", status=200)
                        case 'interference':
                            return HttpResponse("Übermaßpassung", status=200)
                        case 'transition':
                            return HttpResponse("Übergangspassung", status=200)
                case 'fit_system':
                    # logger.debug(f"\033[92mDEBUG: Found fit system: {service.Tolerance.get('fit_system')}\033[0m")
                    match service.Tolerance.get('fit_system'):
                        case 'bore':
                            return HttpResponse("Einheitsbohrung", status=200)
                        case 'shaft':
                            return HttpResponse("Einheitswelle", status=200)
                        case 'combined':
                            return HttpResponse("Kombiniertes System", status=200)
                    return HttpResponse(service.Tolerance.get('fit_system'), status=200)
                case _:
                    msg = f"Unknown Hx-Trigger: '{form_data.get('Hx-Trigger')}'"
                    logger.error(msg)
                    raise Exception(msg)


            # Service in Session speichern
            self.save_session(request, service)
            return HttpResponse(status=200)

        except ValueError as ve:
            logger.exception(f"\033[91mValue error occurred: {str(ve)} in {ve.__traceback__.tb_frame.f_code.co_filename} Zeile {ve.__traceback__.tb_lineno}\033[0m.")

            response = JsonResponse({
                'messageType': 'ValueError',
                'message': 
                    f"Es ist ein Wertefehler aufgetreten: {str(ve)} in {ve.__traceback__.tb_frame.f_code.co_filename} Zeile {ve.__traceback__.tb_lineno}." if settings.DEBUG 
                    else f"Es ist ein Wertefehler aufgetreten: {str(ve)}. Bitte überprüfen Sie Ihre Eingaben.",
                'error': str(ve)
            },
            status=400,
            content_type='application/json',
            headers={'HX-Trigger': json.dumps({'showError': str(ve)})}
            )
            return response

        except Exception as ge:
            logger.exception(f"\033[91mGeneral error occurred: {str(ge)} at line {ge.__traceback__.tb_lineno}\033[0m")
            response = JsonResponse({
                'messageType': 'GeneralError',
                'message': 
                    f"Es ist ein allgemeiner Fehler aufgetreten: {str(ge)} in {ge.__traceback__.tb_frame.f_code.co_filename} Zeile {ge.__traceback__.tb_lineno}." if settings.DEBUG 
                    else f"Es ist ein allgemeiner Fehler aufgetreten: {str(ge)}. Bitte versuchen Sie es erneut.",                
                'error': str(ge)
            },
            status=400,
            content_type='application/json',
            headers={'HX-Trigger': json.dumps({'showError': str(ge)})}
            )
            return response

