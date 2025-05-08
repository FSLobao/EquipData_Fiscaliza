#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 26 10:00:00 2023
@project: Redmine Project Management
@file: retrieve_data.py
@description: This script connects to a Redmine server and retrieves a list of existing projects.
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
LOG_LEVEL:logging = logging.DEBUG
""" Logging level to be used in the script. """
TEST_MODE:bool = True
""" Flag to enable test mode. Default is False. """

REDMINE_URL:str = "https://sistemas.anatel.gov.br/fiscaliza"
""" URL of the Redmine server. Default is "https://sistemas.anatel.gov.br/fiscaliza". """
PRJ_INSTR_GENERAL_REGISTER:str = "Cadastro-Instrumentos"
""" Name of the project for general register. Default is "Cadastro-Instrumentos". """
PROJECT_NAME_KEYWORD:str = "Instrumentos"
""" Keyword to filter projects. Default is "Instrumentos". """
GR_ISSUE_TRACKER_NAMES:list = ["Categoria de instrumento", "Tipo de instrumento", "Marca e Modelo", "Tipo de Acessório"]
""" List of issue tracker names for the general register. Default is ["Categoria de instrumento", "Tipo de instrumento", "Marca e Modelo", "Tipo de Acessório"]. """
EQUIPMENT_TRACKER_ID:int = 20
""" Tracker ID for equipment issues. Default is 20. """
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
    
    # ----------------------------------------------------------------------------------------------
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
            level='INFO',
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
        logging.getLogger().setLevel(LOG_LEVEL)
        logging.getLogger("redminelib").setLevel(LOG_LEVEL)
        
        # Set up the logger
        handler = logging.StreamHandler()
        
        logger = logging.getLogger()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

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
    
    # ------------------------------------------------------------------------------------------
    def fetch_projects(self) -> dict:
        """
        Fetches projects from the Redmine server and filters them based on the keyword in their name.
        """
        
        global PROJECT_NAME_KEYWORD, PRJ_INSTR_GENERAL_REGISTER, PROJECT_NAME_KEYWORD
        
        # Query for existing projects
        logging.info("Fetching projects...")
        projects = self.redmine.project.all()
        
        # Filter projects based on the keyword in their name
        self.equipment_projects_data = {project.name: project.id for project in projects if PROJECT_NAME_KEYWORD in project.name}
        
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
            logging.warning("General register project not found. Should skip it? (y/n)")
            answer = input("Answer: ").strip().lower()
            if answer == "y":
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
    def fetch_issues_by_project(self, project: dict, tracker_id:str = None) -> dict:
        """
        Fetches issues for a given project ID from the Redmine server.

        :param project: Name and ID of the project to fetch issues from.
        :param tracker_id: Tracker ID to filter issues by (optional).
        :return: Updated project dictionary adding a list of issues, under the key 'issues'.
        """
        global TEST_MODE
        
        test_mode_counter = 0
        
        for project_name, project_id in project.items():
            if project_id:
                logging.info(f"Fetching issues for project: '{project_name}' (ID {project_id})...")
                issues = self.redmine.issue.filter(project_id=project_id, status_id='*', tracker_id=tracker_id, limit=1500)
                logging.info(f"Found {len(issues)} issues in project: '{project_name}' (ID {project_id}).")
            
                if len(issues) == 1500:
                    logging.info("Warning: More than 1500 issues found. Consider paginating the results.")
            
                project[project_name]={"id":project_id,"issues":issues}
            else:
                logging.warning(f"Invalid project ID {project_id} provided.")
                project.pop(project_name,None)
        
            if TEST_MODE:
                test_mode_counter += 1
                if test_mode_counter==2:
                    logging.info("Test mode active. Skipping issue data retrieval.")
                    return

            
        return project

    # ------------------------------------------------------------------------------------------
    def parse_issue_data(self, issue) -> dict:
        """
        Parses issue data and appends it to the appropriate DataFrame based on the issue's tracker name.
        
        :param issue: The issue object to parse.
        :return: A dictionary containing the parsed issue data.
        """
        
        issue_data = {
            "id": issue.id,
            "Tipo (tracker)": issue.tracker.name,
            "Situação (status)": issue.status.name,
            "Título (subject)": issue.subject
        }
        
        try:
            for custom_field in issue.custom_fields:
                if custom_field.value is not None:
                    if isinstance(custom_field.value, str) and custom_field.value.startswith('{'):
                        try:
                            custom_field_value = json.loads(custom_field.value)
                            issue_data[custom_field.name] = custom_field_value.get('valor', 'N/A')
                        except json.JSONDecodeError:
                            logging.error(f"Failed to decode JSON for custom field '{custom_field.name}'")
                    else:
                        issue_data[custom_field.name] = custom_field.value
        except Exception as e:
            if type(e).__name__ != "ResourceAttrError":
                logging.warning(f"Error processing issue: '{issue.tracker.name}' (ID {issue.id}): {e}")

        return issue_data

    # ------------------------------------------------------------------------------------------
    def process_general_register(self) -> None:
        """
        Processes the 'Cadastro-instrumentos' project by fetching its issues and appending them to the appropriate DataFrame.
        """
        
        global PRJ_INSTR_GENERAL_REGISTER
        
        try:
            # Fetch issues for the 'Cadastro-instrumentos' project
            self.gr_project_data = self.fetch_issues_by_project(self.gr_project_data)
        
            # Process each issue and store it in the appropriate DataFrame
            for issue in self.gr_project_data[PRJ_INSTR_GENERAL_REGISTER]["issues"]:
                issue_data = self.parse_issue_data(issue)
                try:
                    # Append the issue data to the appropriate DataFrame
                    self.gr_df_dict[issue.tracker.name] = pd.concat([   self.gr_df_dict[issue.tracker.name],
                                                                        pd.DataFrame([issue_data])],
                                                                        ignore_index=True)
                except KeyError:
                    logging.warning(f"Tracker '{issue.tracker.name}' not found in DataFrame dictionary. Skipping issue ID {issue.id}.")
                                
        except KeyError:
            return

    # ------------------------------------------------------------------------------------------
    def process_equipment_data(self) -> None:
        """
        Processes the equipment data by fetching issues from the projects with the associated equipment tracker and appending them to the DataFrame.
        """
        
        global TEST_MODE, PRJ_INSTR_GENERAL_REGISTER, EQUIPMENT_TRACKER_ID
        
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
                    if test_mode_counter==2:
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