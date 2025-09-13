import argparse
import pandas as pd
import numpy as np
import os
import re
import sys
import platform
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction, connection
from fits.models import ISOToleranceClass
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Import ISO tolerance data from multiple Excel/CSV files with sheet support'
    
    # Updated column structure for ISO 286-2 format
    required_columns = {
        'nominal_size_min': 'Nennmaß min [mm]',
        'nominal_size_max': 'Nennmaß max [mm]', 
        'tolerance_class': 'Toleranzklasse',
        'tolerance_grade': 'Toleranzgrad',
        'tolerance_max': 'Grenzmaß max [µm]',
        'tolerance_min': 'Grenzmaß min [µm]',
        'description': 'Beschreibung (optional)',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '-f', '--file',
            dest='file_name',
            nargs='+',
            required=False,
            help='Name(s) of the Excel file(s) to process'
        )
        parser.add_argument(
            '-s', '--sheet',
            dest='sheet_name',
            default=None,
            help='Name or index of the sheet to process (default: None = all sheets)'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing entries with same nominal size range and tolerance class'
        )
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username for created_by/updated_by fields (default: admin)'
        )
        parser.add_argument(
            '--preview',
            action='store_true',
            help='Only show preview without importing data'
        )
        parser.add_argument(
            '--purge',
            action='store_true',
            help='Purge all existing data before import (requires confirmation)'
        )
        parser.add_argument(
            '--purge-only',
            action='store_true',
            help='Only purge data without importing anything'
        )

    def get_char_windows(self, prompt):
        """Get a single character input on Windows without allowing paste"""
        self.stdout.write(prompt, ending='')
        self.stdout.flush()
        
        # Use msvcrt for Windows
        try:
            import msvcrt
            char = msvcrt.getch().decode('utf-8')
            self.stdout.write(char)  # Echo the character
            self.stdout.write('\n')
            return char
        except ImportError:
            # Fallback for Windows without msvcrt
            return input(prompt)[:1]

    def get_char_linux(self, prompt):
        """Get a single character input on Linux/Mac without allowing paste"""
        self.stdout.write(prompt, ending='')
        self.stdout.flush()
        
        try:
            import tty
            import termios
            # Save terminal settings
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            
            try:
                # Set terminal to raw mode
                tty.setraw(sys.stdin.fileno())
                char = sys.stdin.read(1)
                
                # Clear any remaining input in buffer
                termios.tcflush(sys.stdin, termios.TCIFLUSH)
                
            finally:
                # Restore terminal settings
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
            self.stdout.write(char)  # Echo the character
            self.stdout.write('\n')
            return char
            
        except ImportError:
            # Fallback if termios not available
            return input(prompt)[:1]

    def get_char(self, prompt):
        """Get a single character input based on platform"""
        if platform.system() == 'Windows':
            return self.get_char_windows(prompt)
        else:
            return self.get_char_linux(prompt)

    def confirm_purge(self):
        """Ask for confirmation to purge data with safety question"""
        self.stdout.write(self.style.WARNING("\n" + "!" * 60))
        self.stdout.write(self.style.WARNING("WARNING: You are about to PURGE ALL ISO TOLERANCE DATA!"))
        self.stdout.write(self.style.WARNING("This action cannot be undone!"))
        self.stdout.write(self.style.WARNING("!" * 60))
        
        # Ask safety question
        safety_answer = self.get_char("Type 'DELETE' to confirm purge (case-sensitive): ")
        
        if safety_answer != 'D':
            self.stdout.write(self.style.ERROR("Purge cancelled. First character must be 'D'"))
            return False
        
        # Get remaining characters one by one
        chars = ['D']
        for i, expected_char in enumerate('ELETE'):
            char = self.get_char(f"Character {i+2}/6: ")
            chars.append(char)
            if char != expected_char:
                self.stdout.write(self.style.ERROR(f"Purge cancelled. Expected '{expected_char}', got '{char}'"))
                return False
        
        full_answer = ''.join(chars)
        if full_answer == 'DELETE':
            self.stdout.write(self.style.SUCCESS("Safety question passed."))
            
            # Final confirmation
            final_confirmation = self.get_char("Are you absolutely sure? Type 'Y' to confirm: ")
            if final_confirmation.upper() == 'Y':
                return True
            else:
                self.stdout.write(self.style.ERROR("Purge cancelled."))
                return False
        else:
            self.stdout.write(self.style.ERROR(f"Purge cancelled. Expected 'DELETE', got '{full_answer}'"))
            return False

    def purge_data(self):
        """Purge all ISO tolerance data using raw SQL to avoid recursion"""
        try:
            # Get the table name
            table_name = ISOToleranceClass._meta.db_table
            
            # Use raw SQL to avoid Django ORM recursion issues
            with connection.cursor() as cursor:
                # Count records first
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                
                # Delete all records
                cursor.execute(f"DELETE FROM {table_name}")
                
                # Reset sequence if using PostgreSQL
                if connection.vendor == 'postgresql':
                    cursor.execute(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), 1, false)")
                
                self.stdout.write(self.style.SUCCESS(f"Purged {count} ISO tolerance records"))
                return True
                
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error during purge: {str(e)}"))
            return False

    def get_all_sheet_names(self, file_name):
        """Get all sheet names from Excel file"""
        try:
            excel_file = pd.ExcelFile(file_name, engine='openpyxl')
            return excel_file.sheet_names
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error reading sheets from {file_name}: {str(e)}"))
            return []

    def process_excel_file(self, file_name, sheet_name=None):
        """Process Excel file based on ISO 286-2 format"""
        try:
            if sheet_name is None:
                # Process all sheets
                all_dfs = []
                sheet_names = self.get_all_sheet_names(file_name)
                
                for sheet in sheet_names:
                    self.stdout.write(f"Processing sheet: {sheet}")
                    df_sheet = self._process_single_sheet(file_name, sheet)
                    if not df_sheet.empty:
                        all_dfs.append(df_sheet)
                
                if all_dfs:
                    return pd.concat(all_dfs, ignore_index=True)
                else:
                    return pd.DataFrame()
            else:
                # Process single sheet
                return self._process_single_sheet(file_name, sheet_name)
                
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error processing Excel file {file_name}: {str(e)}"))
            return pd.DataFrame()

    def _process_single_sheet(self, file_name, sheet_name):
        """Process a single sheet from Excel file"""
        try:
            # Read raw data without header to extract the class
            df_raw = pd.read_excel(file_name, sheet_name=sheet_name, header=None, engine='openpyxl')

            # Convert columns to object dtype before filling
            df_raw = df_raw.astype('object')
            
            # Forward fill nominal size columns (columns 0 and 1)
            df_raw[[0, 1]] = df_raw[[0, 1]].ffill()
            
            # Forward fill tolerance class headers (row 0, columns 2+)
            df_raw.iloc[0, 2:] = df_raw.iloc[0, 2:].ffill()

            # Concatenate rows 0 and 1 for columns from index 2 onwards
            header_row = df_raw.iloc[1].copy()
            for col in range(2, len(df_raw.columns)):
                # Convert to string and clean up values
                class_value = str(df_raw.iloc[0, col])
                tolerance_value = str(df_raw.iloc[1, col])
                
                # Clean up values (remove .0, extra spaces, etc.)
                if '.' in class_value:
                    class_value = class_value.rstrip('0').rstrip('.')
                if '.' in tolerance_value:
                    tolerance_value = tolerance_value.rstrip('0').rstrip('.')
                
                # Create combined header
                header_row[col] = f"{class_value.strip()}{tolerance_value.strip()}"

            # Replace row 1 with concatenated header
            df_raw.iloc[1] = header_row
            df_raw = df_raw.iloc[1:].reset_index(drop=True)

            # Create rows with all tolerance classes
            tolerance_rows = []
            data_rows = df_raw.values

            for i in range(1, len(data_rows), 2):
                if i + 1 < len(data_rows):  # Check if we have a pair
                    # Add all tolerance classes from columns 2 onwards
                    for j in range(2, len(data_rows[i])):
                        # Skip empty cells
                        if pd.isna(data_rows[i][j]) and pd.isna(data_rows[i + 1][j]):
                            continue
                            
                        # Extract tolerance class and grade from combined header
                        full_class = str(data_rows[0][j]).strip()
                        tolerance_class, tolerance_grade = self.split_tolerance_class(full_class)
                        
                        # Create a new row with nominal sizes
                        row_dict = {
                            'nominal_size_min': data_rows[i][0],
                            'nominal_size_max': data_rows[i][1],
                            'tolerance_class': tolerance_class,
                            'tolerance_grade': tolerance_grade,
                            'tolerance_max': data_rows[i][j],
                            'tolerance_min': data_rows[i + 1][j],
                            'description': f"ISO 286-2 - Sheet: {sheet_name}"
                        }

                        tolerance_rows.append(row_dict)

            # Create new DataFrame from rows
            df = pd.DataFrame(tolerance_rows)

            # Clean up data: remove rows with NaN in required columns
            required_cols = ['nominal_size_min', 'nominal_size_max', 'tolerance_class', 
                           'tolerance_grade', 'tolerance_max', 'tolerance_min']
            df = df.dropna(subset=required_cols)

            # Clean numeric values
            for col in ['nominal_size_min', 'nominal_size_max', 'tolerance_max', 'tolerance_min']:
                df[col] = df[col].apply(self.clean_numeric_value)

            # Clean tolerance class and grade - PRESERVE CASE SENSITIVITY for ISO classes
            df['tolerance_class'] = df['tolerance_class'].apply(self.clean_tolerance_class)
            df['tolerance_grade'] = df['tolerance_grade'].apply(self.clean_tolerance_grade)

            return df

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error processing sheet {sheet_name} in {file_name}: {str(e)}"))
            return pd.DataFrame()

    def split_tolerance_class(self, full_class):
        """Split tolerance class into letter part and numeric grade - PRESERVE CASE"""
        if pd.isna(full_class) or not isinstance(full_class, str):
            return '', ''
        
        # Remove any whitespace but preserve case
        full_class = full_class.strip()
        
        # Pattern to match: one or two letters (case sensitive) followed by one or two digits
        pattern = r'^([A-Za-z]{1,2})(\d{1,2})$'
        match = re.match(pattern, full_class)
        
        if match:
            # Return with original case - H7 vs h7 are different in ISO 286!
            return match.group(1), match.group(2)
        else:
            # Fallback: try to extract letters (preserving case) and numbers
            letters = ''.join(re.findall(r'[A-Za-z]', full_class))
            numbers = ''.join(re.findall(r'\d', full_class))
            return letters, numbers if numbers else ''

    def clean_numeric_value(self, value):
        """Clean and convert numeric values"""
        if pd.isna(value):
            return np.nan
        
        # Convert to string and clean
        str_value = str(value).strip()
        str_value = re.sub(r'[^\d.\-]', '', str_value)  # Remove non-numeric characters
        
        try:
            # Handle negative values
            if str_value.startswith('-'):
                return -float(str_value[1:])
            return float(str_value)
        except (ValueError, TypeError):
            return np.nan

    def clean_tolerance_class(self, value):
        """Clean and standardize tolerance class - PRESERVE CASE for ISO 286"""
        if pd.isna(value):
            return ''
        
        # Only clean, don't change case - H vs h are different in ISO standard!
        str_value = str(value).strip()
        # Only allow letters, preserve case
        return re.sub(r'[^A-Za-z]', '', str_value)

    def clean_tolerance_grade(self, value):
        """Clean and standardize tolerance grade"""
        if pd.isna(value):
            return ''
        
        str_value = str(value).strip()
        # Only allow digits
        return re.sub(r'[^\d]', '', str_value)

    def import_data(self, df, user, overwrite, file_name):
        """Import data into database"""
        created_count = 0
        updated_count = 0
        error_count = 0

        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Daten konvertieren und validieren
                    data = {
                        'nominal_size_min': self.safe_int(row.get('nominal_size_min')),
                        'nominal_size_max': self.safe_int(row.get('nominal_size_max')),
                        'tolerance_class': str(row.get('tolerance_class', '')).strip(),
                        'tolerance_grade': str(row.get('tolerance_grade', '')).strip(),
                        'tolerance_max': self.safe_float(row.get('tolerance_max')),
                        'tolerance_min': self.safe_float(row.get('tolerance_min')),
                        'description': str(row.get('description', '')).strip()
                    }

                    # Validierung der Nennmaße
                    if data['nominal_size_min'] >= data['nominal_size_max']:
                        raise ValueError(
                            f"Toleranz {data['tolerance_class']}{data['tolerance_grade']} "
                            f"Nennmaß max ({data['nominal_size_max']}) muss größer als "
                            f"Nennmaß min ({data['nominal_size_min']}) sein"
                        )

                    if data['nominal_size_min'] < 0 or data['nominal_size_max'] > 31500:
                        raise ValueError(
                            f"Toleranz {data['tolerance_class']}{data['tolerance_grade']} "
                            f"Nennmaß min ({data['nominal_size_min']}) muss >= 0 und "
                            f"max darf nicht größer als 31500 mm ({data['nominal_size_max']}) sein"
                        )

                    # Validierung der Toleranzwerte
                    # Toleranzwert-Validierung abhängig von Toleranzklasse
                    # ISO 286: Klassen A~Q, a~q sind "Loch" (hole), andere sind "Welle" (shaft)
                    # Für Loch: min < max, für Welle: min > max
                    if re.match(r'^[A-Qa-q]$', data['tolerance_class']):
                        if data['tolerance_min'] >= data['tolerance_max']:
                            raise ValueError(
                                f"Toleranz {data['tolerance_class']}{data['tolerance_grade']} "
                                f"min ({data['tolerance_min']}) muss kleiner als "
                                f"max ({data['tolerance_max']})"
                            )
                    else:
                        if data['tolerance_min'] >= data['tolerance_max']:
                            raise ValueError(
                                f"Toleranz {data['tolerance_class']}{data['tolerance_grade']} "
                                f"min ({data['tolerance_min']}) muss größer als "
                                f"max ({data['tolerance_max']})"
                            )

                    # Validierung der Toleranzklasse und Grad
                    if not data['tolerance_class']:
                        raise ValueError("Toleranzklasse darf nicht leer sein")
                    
                    if not data['tolerance_grade']:
                        raise ValueError("Toleranzgrad darf nicht leer sein")
                    
                    # Updated validation to allow case-sensitive ISO classes
                    if not re.match(r'^[A-Za-z]{1,2}$', data['tolerance_class']):
                        raise ValueError(
                            f"Toleranzklasse '{data['tolerance_class']}' muss 1-2 Buchstaben sein (z.B. H, h, JS, js, CD, cd)"
                        )
                    
                    if not re.match(r'^\d{1,2}$', data['tolerance_grade']):
                        raise ValueError(
                            f"Toleranzgrad '{data['tolerance_grade']}' muss 1-2 Ziffern sein (z.B. 7, 11)"
                        )

                    # Import durchführen
                    if overwrite:
                        obj, created = ISOToleranceClass.objects.update_or_create(
                            nominal_size_min=data['nominal_size_min'],
                            nominal_size_max=data['nominal_size_max'],
                            tolerance_class=data['tolerance_class'],  # Case-sensitive!
                            tolerance_grade=data['tolerance_grade'],
                            defaults={
                                'tolerance_max': data['tolerance_max'],
                                'tolerance_min': data['tolerance_min'],
                                'description': data['description'],
                                'created_at': timezone.now(),
                                'updated_at': timezone.now(),
                                'created_by': user.username,  # Fixed: use username string
                                'updated_by': user.username,  # Fixed: use username string
                            }
                        )
                    else:
                        obj, created = ISOToleranceClass.objects.get_or_create(
                            nominal_size_min=data['nominal_size_min'],
                            nominal_size_max=data['nominal_size_max'],
                            tolerance_class=data['tolerance_class'],  # Case-sensitive!
                            tolerance_grade=data['tolerance_grade'],
                            defaults={
                                'tolerance_max': data['tolerance_max'],
                                'tolerance_min': data['tolerance_min'],
                                'description': data['description'],
                                'created_at': timezone.now(),
                                'updated_at': timezone.now(),
                                'created_by': user.username,  # Fixed: use username string
                                'updated_by': user.username,  # Fixed: use username string
                            }
                        )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                except Exception as e:
                    error_count += 1
                    self.stderr.write(self.style.ERROR(
                        f"Error in {file_name}, row {index + 1}: {str(e)}"
                    ))
                    continue
        
        return created_count, updated_count, error_count

    def safe_int(self, value):
        """Safely convert to integer"""
        try:
            if pd.isna(value):
                return 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def safe_float(self, value):
        """Safely convert to float"""
        try:
            if pd.isna(value):
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def handle(self, *args, **options):
        file_names = options['file_name']
        sheet_name = options['sheet_name']
        overwrite = options['overwrite']
        username = options['username']
        preview_mode = options['preview']
        purge = options['purge']
        purge_only = options['purge_only']
        
        try:
            user = User.objects.get(username=username)
            if not user.is_active:
                raise User.DoesNotExist
            elif not user.is_superuser:
                raise Exception(f"User '{username}' is not a superuser")
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"User '{username}' does not exist"))
            return
        
        # Handle purge operations
        if purge or purge_only:
            if not self.confirm_purge():
                return
            
            if not self.purge_data():
                self.stderr.write(self.style.ERROR("Purge failed"))
                return
            
            if purge_only:
                self.stdout.write(self.style.SUCCESS("Purge completed successfully"))
                return
        
        # Check if files are provided for import
        if not file_names and not purge_only:
            self.stderr.write(self.style.ERROR("No files specified for import"))
            return
        
        total_created = 0
        total_updated = 0
        total_errors = 0
        processed_files = 0
        
        for file_name in file_names:
            if not os.path.exists(file_name):
                self.stderr.write(self.style.WARNING(f"File not found: {file_name}"))
                continue
            
            try:
                if sheet_name is None:
                    self.stdout.write(self.style.SUCCESS(f"Processing all sheets in {file_name}"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"Processing {file_name}, sheet: {sheet_name}"))
                
                # Excel-Datei verarbeiten
                df = self.process_excel_file(file_name, sheet_name)
                
                if df.empty:
                    self.stderr.write(self.style.WARNING(f"No data found in {file_name}"))
                    continue
                
                if preview_mode:
                    self.stdout.write(self.style.SUCCESS("PREVIEW MODE - No data will be imported"))
                    self.stdout.write(f"Data shape: {df.shape}")
                    self.stdout.write(f"Columns: {list(df.columns)}")
                    self.stdout.write("\nFirst 5 rows:")
                    self.stdout.write(df.head().to_string())
                    continue
                
                # Daten importieren
                file_created, file_updated, file_errors = self.import_data(
                    df, user, overwrite, file_name
                )
                
                # Zusammenfassung pro Datei
                self.stdout.write(self.style.SUCCESS(
                    f"{file_name}: {file_created} created, {file_updated} updated, {file_errors} errors"
                ))
                
                total_created += file_created
                total_updated += file_updated
                total_errors += file_errors
                processed_files += 1
                
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error processing {file_name}: {str(e)}"))
                continue
        
        # Gesamtzusammenfassung
        if not preview_mode and file_names:
            self.stdout.write(self.style.SUCCESS("\n" + "="*50))
            self.stdout.write(self.style.SUCCESS("IMPORT SUMMARY"))
            self.stdout.write(self.style.SUCCESS("="*50))
            self.stdout.write(self.style.SUCCESS(f"Processed files: {processed_files}/{len(file_names)}"))
            self.stdout.write(self.style.SUCCESS(f"Total created: {total_created}"))
            self.stdout.write(self.style.SUCCESS(f"Total updated: {total_updated}"))
            self.stdout.write(self.style.SUCCESS(f"Total errors: {total_errors}"))
            
            if total_errors > 0:
                self.stdout.write(self.style.WARNING(
                    f"Import completed with {total_errors} errors"
                ))
            else:
                self.stdout.write(self.style.SUCCESS("Import completed successfully!"))