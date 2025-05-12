#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@description: This is an ETL script to extract data from Redmine, transform it into a structured format, and load it into an Excel file.
@license: MIT License
@version: 1.0
@maintainer: Fábio Santos Lobão
@maintainer_email: fabioslobao@hotmail.com
"""

# ----------------------------------------------------------------------------------------------
# Import necessary libraries
import logging
import coloredlogs
import os
from pathlib import Path
import datetime

from redminelib import Redmine
import getpass
import json

import pandas as pd

# ----------------------------------------------------------------------------------------------
# Constants and configuration variables

APP_TITLE:str = " FIDEx Tool "
""" Title to be shown in the splash screen. """
LINE_STYLE:str = "~"
""" Character to be used as horizontal line style on the UI. """
LOG_LEVEL:str = "DEBUG"
""" Logging level to be used in the script. """
TEST_MODE:bool = False
""" Flag to enable test mode. Default is False. """
TEST_LENGTH:int = 2
""" Number of projects to be processed in test mode. Default is 2. """

REDMINE_URL:str = "https://sistemas.anatel.gov.br/fiscaliza"
""" URL of the Redmine server. Default is "https://sistemas.anatel.gov.br/fiscaliza". """
PRJ_INSTR_GENERAL_REGISTER:str = "Cadastro-Instrumentos"
""" Name of the project for general register. Default is "Cadastro-Instrumentos". """
PROJECT_NAME_KEYWORD:str = "Instrumentos"
""" Keyword to filter projects. Default is "Instrumentos". """
PRJ_TO_SKIP:list = [94, 123, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122]
""" List of project IDs to skip. Default is []. """
GR_ISSUE_TRACKER_NAMES:list = ["Categoria de instrumento", "Tipo de instrumento", "Marca e Modelo", "Tipo de Acessório"]
""" List of issue tracker names for the general register. Default is ["Categoria de instrumento", "Tipo de instrumento", "Marca e Modelo", "Tipo de Acessório"]. """
EQUIPMENT_TRACKER_ID:int = 20
""" Tracker ID for equipment issues. Default is 20. """
JOURNAL_CAL_DATE_ID:str = "581"
""" ID of the journal field for calibration date. Default is 581. """
JOURNAL_CAL_CERT_SEI_ID:str = "583"
""" ID of the journal field for calibration certificate SEI number. Default is 583. """
OUTPUT_FILENAME_SUFFIX:str = "instrumentos_anatel"
""" Name of the output Excel file. Default is "redmine_data.xlsx". """
OUTPUT_PATH:str = Path.home()
""" Path to the output directory. Default user home folder. """

# ----------------------------------------------------------------------------------------------
class uiTerminal:
    """ Class to handle UI over the terminal (CLI). """	
    
    def __init__(self):
        """ Initializes the uiTerminal class. """
        
        global LINE_STYLE, APP_TITLE
        
        self.terminal_width: str = os.get_terminal_size().columns
        """ Terminal width. """
        self.app_title: str = self.draw_title(APP_TITLE)
        """ Title to be shown in the help message. """
        self.line: str = LINE_STYLE * self.terminal_width
        """ Line to be shown in the help message. """
        self.username: str = None
        """ Username to be used in the connection. """
        self.password: str = None
        """ Password to be used in the connection. """
        
    # ------------------------------------------------------------------------------------------
    def draw_title(self, title: str) -> str:
        """
        Draw a title centered in the terminal.
        
        :param title: Title to be drawn.
        :return: Title drawn.
        """
        
        global LINE_STYLE
        
        title_side_bar_length = (self.terminal_width - len(title)) // 2
        side_bar = LINE_STYLE * title_side_bar_length
        title_line = f"{side_bar}{title}{side_bar}"
        if len(title_line) < self.terminal_width:
            title_line += LINE_STYLE
            
        return title_line
    
    # ------------------------------------------------------------------------------------------
    def get_credentials(self) -> tuple:
        """
        Get user credentials.

        :return: Tuple with username and password.
        """
        
        print(f"\033[90m\n{self.app_title}")
        print("\nWelcome to the Fiscaliza Instrument Data Extraction Tool!\n")
        self.username = input("Username: ").strip()
        self.password = getpass.getpass("Password: ").strip()
        print(f"{self.line}\n\033[0m")
    
    # ------------------------------------------------------------------------------------------
    def query_yes_no(self, question: str) -> bool:
        """
        Ask a yes/no question and return the answer.

        :param question: The question to ask.
        :return: True if the answer in ['yes','y','YES','Y'] or False if the answer in ['no','n','NO','N'], ignoring spaces. Keep asking until a valid answer is given.
        """
        
        answer = None
        print(f"\033[90m\n{self.line}")
        while answer is None:
            answer = input(f"{question} (y/n): ").strip().lower()
            if answer in ['y', 'yes']:
                answer = True
            elif answer in ['n', 'no']:
                answer = False
            else:
                print("Please respond with 'y' or 'n'.")
                
        print(f"{self.line}\n\033[0m")
        return answer
    
    # ------------------------------------------------------------------------------------------
    def setup_logging(self) -> None:
        """
        Sets up the logging configuration for the script.
        """
        global LOG_LEVEL
        
        # Remove any existing handlers from the root logger
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        # Define a custom formatter for colored logging
        coloredlogs.install(
            level=LOG_LEVEL,
            fmt=' %(asctime)s | %(levelname)8s |  %(message)s',
            field_styles={'asctime': {'color': 'green'}},
            level_styles={
                'info': {'color': 'blue'},
                'warning': {'color': 'yellow'},
                'error': {'color': 'red'},
                'critical': {'color': 'red', 'bold': True}
            }
        )
        
        # Ensure all loggers (including third-party modules) use the same formatting
        logging.basicConfig(
            level=LOG_LEVEL,  # Set the minimum logging level
            format='%(asctime)s | %(levelname)8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Set the logging level for specific modules (e.g., redminelib)
        logging.getLogger("redminelib").setLevel(LOG_LEVEL)
        
    # ------------------------------------------------------------------------------------------
    def start_logging(self) -> None:
        """
        Print log header and start logging.
        """
        
        print(f"\033[90m{self.line}\033[0m")
        print("\033[92mTIMESTAMP\033[0m            | LEVEL    | \033[94mMESSAGE\033[0m")
        self.setup_logging()

# ----------------------------------------------------------------------------------------------
class RedmineParser:
    """
    Class to handle parsing of Redmine issues and storing them in DataFrames.
    """
    
    # ------------------------------------------------------------------------------------------
    def __init__(self, ui: uiTerminal) -> None:
        """
        Initializes the RedmineParser class.
        
        :param ui: Instance of the uiTerminal class for user interaction.
        :param project_dict: Dictionary of project names and their IDs.
        :param df_dict: Dictionary of DataFrames for different trackers.
        """
        global REDMINE_URL, GR_ISSUE_TRACKER_NAMES
        
        self.ui: uiTerminal = ui
        """ Instance of the uiTerminal class for user interaction. """
        self.redmine: Redmine = Redmine(REDMINE_URL, username=ui.username, password=ui.password)
        """ Redmine object connected to the server for data retrieval. """
        self.equipment_projects_data: dict = {}
        """ Dictionary to store project IDs for different equipment projects. """
        self.gr_project_data: dict = {}
        """ Dictionary to store project IDs for general register projects. """
        self.gr_df_dict: dict = {tracker: pd.DataFrame() for tracker in GR_ISSUE_TRACKER_NAMES}
        """ Output dictionary of DataFrames for various parsed general register tables (associated with different trackers). """
        self.instr_df: pd.DataFrame = pd.DataFrame()
        """ Output dataFrame for parsed equipment data entries (issues with equipment_TRACKER_ID). """
        self.custom_fields_codes: dict = {}
        """ Dictionary to store custom fields for the issues. """
    
    # ------------------------------------------------------------------------------------------
    def fetch_projects(self) -> dict:
        """
        Fetches projects from the Redmine server and filters them based on the keyword in their name.
        """
        
        global PROJECT_NAME_KEYWORD, PRJ_INSTR_GENERAL_REGISTER, PROJECT_NAME_KEYWORD, PRJ_TO_SKIP
        
        # Query for existing projects
        logging.info("Fetching projects...")
        projects = self.redmine.project.all()
        
        # Filter projects based on the keyword in their name
        self.equipment_projects_data = {project.name: project.id for project in projects if (PROJECT_NAME_KEYWORD in project.name and project.id not in PRJ_TO_SKIP)}
        
        logging.debug(f"Fetched projects: {json.dumps(self.equipment_projects_data, indent=4)}")
        
        # Set up the project dictionary for the general register from the equipment project IDs
        try:
            self.gr_project_data = {PRJ_INSTR_GENERAL_REGISTER: self.equipment_projects_data[PRJ_INSTR_GENERAL_REGISTER]}
            self.equipment_projects_data.pop(PRJ_INSTR_GENERAL_REGISTER, None)
        except KeyError:
            logging.error(f"Project '{PRJ_INSTR_GENERAL_REGISTER}' not found in the fetched projects.")
            self.gr_project_data = None
        
        # Check projects found
        if self.gr_project_data:
            logging.info("General register project id found'.")
        else:
            if self.ui.query_yes_no(f"Project '{PRJ_INSTR_GENERAL_REGISTER}' not found. Do you want to skip it?"):
                logging.info("Skipping general register project.")
            else:
                logging.error("General register project not found. Exiting.")
                exit(1)
        
        if self.equipment_projects_data:
            logging.info(f"Found {len(self.equipment_projects_data)} projects with keyword '{PROJECT_NAME_KEYWORD}'.")
        else:
            logging.warning(f"Project with keyword {PROJECT_NAME_KEYWORD} not found.")
            exit(1)
    
    # ------------------------------------------------------------------------------------------
    def fetch_issues_by_project(self, project: dict, tracker_id:str = None, include_journals:bool = True) -> dict:
        """
        Fetches issues for a given project ID from the Redmine server.

        :param project: Name and ID of the project to fetch issues from.
        :param tracker_id: Tracker ID to filter issues by (optional).
        :return: Updated project dictionary adding a list of issues, under the key 'issues'.
        :raise: Exception if an error occurs different from AttributeError.
        """
        global TEST_MODE, TEST_LENGTH
        
        test_mode_counter = 0
        
        try:
            for project_name, project_id in project.items():
                if project_id:
                    logging.info(f"Fetching issues for project: '{project_name}' (ID {project_id})...")
                    
                    issue_filter_params = {
                        "project_id": project_id,
                        "status_id": "*",
                        "limit": 1500
                    }
                    if tracker_id:
                        issue_filter_params["tracker_id"] = tracker_id
                    if include_journals:
                        issue_filter_params["include"] = "journals"
                        
                    issues = self.redmine.issue.filter(**issue_filter_params)
                    logging.info(f"Found {len(issues)} issues in project: '{project_name}' (ID {project_id}).")
                
                    if len(issues) == 1500:
                        logging.info("Warning: More than 1500 issues found. Consider paginating the results.")
                
                    project[project_name]={"id":project_id,"issues":issues}
                else:
                    logging.warning(f"Invalid project ID {project_id} provided.")
                    project.pop(project_name,None)
            
                if TEST_MODE:
                    test_mode_counter += 1
                    if test_mode_counter == TEST_LENGTH:
                        logging.info("Test mode active. Skipping issue data retrieval of the remaining projects.")
                        return project
        except AttributeError:
            project = {"None": 0, "issues": []}
        except Exception as e:
            try:
                logging.error(f"Error fetching issues for project '{project_name}' (ID {project_id}): {e}")
            except Exception as e:
                logging.error(f"Error due project item without name or id: {e}")
            raise
            
        return project

    def parse_calibration_historical_data(self, journals: object, issue_id: str) -> dict:
        """
        Parses journal data from an issue.

        :param journal: The journal object to parse.
        :param issue_data: The issue data dictionary to update with parsed values.
    
        :return: A dictionary containing the parsed journal data.
        """
        global JOURNAL_CAL_DATE_ID, JOURNAL_CAL_CERT_SEI_ID
                
        issue_data = {}        
        for journal in journals:
            logging.debug(f"#{issue_id} details: {journal.details}")
            calibration_date_found = False
            calibration_number_found = False

            for detail in journal.details:
                if detail['name'] == JOURNAL_CAL_DATE_ID:
                    calibration_date = detail['old_value']
                    if not calibration_date:
                        continue
                    else:
                        # Build keys for calibration number and date based on the year
                        calibration_year = detail['old_value'].split('-')[0]
                        cal_number_key = f"Nº SEI Certificado calibração {calibration_year}"
                        cal_date_key = f"Data de calibração {calibration_year}"
                        
                        calibration_date_found = True
                    
                elif detail['name'] == JOURNAL_CAL_CERT_SEI_ID:
                    calibration_number = detail['old_value']
                    calibration_number_found = True
                    
                if calibration_date_found and calibration_number_found:
                    issue_data[cal_number_key] = calibration_number
                    issue_data[cal_date_key] = calibration_date
                    break
        
        return issue_data

    def parse_json_custom_field(self, custom_field_value: str) -> str:
        """
        Parses a custom field value that may contain JSON data.

        :param custom_field: The custom field object to parse.
        :return: Parsed value for the custom field.
        """
        try:
            custom_field_json_value = json.loads(custom_field_value)
        except json.JSONDecodeError:
            # Handle special case of near JSON format
            custom_field_value = custom_field_value.replace('=>', ':')
            custom_field_value = custom_field_value.replace('"numero"', '"valor"')
            custom_field_value = custom_field_value.replace('19"LED', '19\\"LED')
            try:
                custom_field_json_value = json.loads(custom_field_value)
            except json.JSONDecodeError:
                raise ValueError(f"Error after string replacement for custom field value: {custom_field_value}")
        except Exception as e:
            logging.error(f"Failed to decode custom field '{custom_field_value}': {e}")
            custom_field_json_value = {}

        return custom_field_json_value.get('valor', "")
    
    # ------------------------------------------------------------------------------------------
    def parse_issue_data(self, issue) -> dict:
        """
        Parses issue data and appends it to the appropriate DataFrame based on the issue's tracker name.
        
        :param issue: The issue object to parse.
        :return: A dictionary containing the parsed issue data.
        """
        
        try:
            # Parse mandatory fields from the issue
            issue_data = {
                "id": issue.id,
                "Tipo (tracker)": issue.tracker.name,
                "Situação (status)": issue.status.name,
                "Título (subject)": issue.subject
            }

            # Parse custom fields
            for custom_field in issue.custom_fields:
                if isinstance(custom_field.value, list):
                    parsed_values = []
                    for item in custom_field.value:
                        if str(item).startswith('{'):
                            parsed_values.append(self.parse_json_custom_field(item))
                        else:
                            parsed_values.append(item)
                    parsed_custom_field_value = ', '.join(parsed_values)
                else:
                    if str(custom_field.value).startswith('{'):
                        parsed_custom_field_value = self.parse_json_custom_field(custom_field.value)
                    else:
                        parsed_custom_field_value = custom_field.value
                
                issue_data[custom_field.name] = parsed_custom_field_value
                self.custom_fields_codes[custom_field.id] = custom_field.name
                    
            logging.debug(f"Parsed custom fields data: {json.dumps(self.custom_fields_codes, indent=4)}")
            
            # Parse historical calibration data from journals, if journals exist
            if issue.journals.total_count:
                issue_data.update(self.parse_calibration_historical_data(issue.journals, issue_data["id"]))
                
        except Exception as e:
            # If missing attributes in RedMine data, skip the issue
            if type(e).__name__ != "ResourceAttrError":
                logging.warning(f"Error processing issue: '{issue.tracker.name}' (ID {issue.id}): {e}")

        return issue_data

    # ------------------------------------------------------------------------------------------
    def process_general_register(self) -> None:
        """
        Processes the 'Cadastro-instrumentos' project by fetching its issues and appending them to the appropriate DataFrame.
        """
        
        global PRJ_INSTR_GENERAL_REGISTER
        
        skipped_count = 0
        processed_count = 0
        
        try:
            # Fetch issues for the 'Cadastro-instrumentos' project
            self.gr_project_data = self.fetch_issues_by_project(self.gr_project_data, include_journals=False)
        
            # Process each issue and store it in the appropriate DataFrame
            for issue in self.gr_project_data[PRJ_INSTR_GENERAL_REGISTER]["issues"]:
                issue_data = self.parse_issue_data(issue)
                try:
                    # Append the issue data to the appropriate DataFrame
                    self.gr_df_dict[issue.tracker.name] = pd.concat([   self.gr_df_dict[issue.tracker.name],
                                                                        pd.DataFrame([issue_data])],
                                                                        ignore_index=True)
                    processed_count += 1
                except KeyError:
                    logging.debug(f"Tracker '{issue.tracker.name}' not found in DataFrame dictionary. Skipping issue ID {issue.id}.")
                    skipped_count += 1
                    
            logging.info(f"Processed {processed_count} issues, skipped {skipped_count} from the general register.")
        except KeyError:
            return

    # ------------------------------------------------------------------------------------------
    def process_equipment_data(self) -> None:
        """
        Processes the equipment data by fetching issues from the projects with the associated equipment tracker and appending them to the DataFrame.
        """
        
        global TEST_MODE, TEST_LENGTH, PRJ_INSTR_GENERAL_REGISTER, EQUIPMENT_TRACKER_ID
        
        test_mode_counter = 0
        try:
            # Fetch issues for the equipment projects
            self.equipment_projects_data = self.fetch_issues_by_project(self.equipment_projects_data, tracker_id=EQUIPMENT_TRACKER_ID)
            
            # Process each issue and store it in the appropriate DataFrame
            for project_name, project in self.equipment_projects_data.items():
                logging.info(f"Processing issues for project: '{project_name}' (ID {project['id']})...")
                
                # Process each issue and store it in the appropriate DataFrame
                for issue in project["issues"]:
                    issue_data = self.parse_issue_data(issue)
                    self.instr_df = pd.concat([self.instr_df, pd.DataFrame([issue_data])], ignore_index=True)
                    
                if TEST_MODE:
                    test_mode_counter += 1
                    if test_mode_counter == TEST_LENGTH:
                        logging.info("Test mode active. Skipping data processing.")
                        return
        
        except KeyError:
            logging.error(f"Project '{PRJ_INSTR_GENERAL_REGISTER}' not found in the fetched projects.")
            return
        
    # ------------------------------------------------------------------------------------------
    def save_data_to_file(self) -> None:
        """
        Saves the DataFrames to an Excel file in the specified output directory.
        """
        global OUTPUT_PATH, OUTPUT_FILENAME_SUFFIX
        
        # create the filename adding a timestamp to the filename
        now = datetime.datetime.now()
        filename = Path(f"{now.strftime('%Y%m%d_%H%M%S')}_{OUTPUT_FILENAME_SUFFIX}.xlsx")
        
        filename = OUTPUT_PATH / filename
        
        # Save each DataFrame to a separate sheet in the Excel file
        with pd.ExcelWriter(filename) as writer:
            # Save the general register DataFrames
            for tracker_name, df in self.gr_df_dict.items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=tracker_name, index=False)
            
            # Save the equipment DataFrame
            self.instr_df.to_excel(writer, sheet_name=PROJECT_NAME_KEYWORD, index=False)
        
        return filename
    
def main():
    
    try:
        ui = uiTerminal()
        ui.get_credentials()
        ui.start_logging()
        
        rp = RedmineParser(ui)
        rp.fetch_projects()
        rp.process_general_register()
        rp.process_equipment_data()
        filename = rp.save_data_to_file()
        
        logging.info(f"Data saved to {filename}")
        logging.info("Process completed successfully.") 
        
    except Exception as e:
        logging.error(f"Unhandled error occurred: {e}")

if __name__ == "__main__":
    main()