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
# Import necessary libraries
from redminelib import Redmine
import logging
import getpass
from colorlog import ColoredFormatter
import json
import pandas as pd

# Constants
REDMINE_URL = "https://sistemas.anatel.gov.br/fiscaliza"
PRJ_INSTR_GENERAL_REGISTER="Cadastro-Instrumentos"


def fetch_issues_by_project(redmine: Redmine, project: dict) -> dict:
    """
    Fetches issues for a given project ID from the Redmine server.

    :param redmine: Redmine object connected to the server.
    :param project_id: The ID of the project to fetch issues from.
    :return: A list of issues for the specified project.
    """
    
    for project_name, project_id in project.items():
        if project_id:
            logging.info(f"Fetching issues for project: '{project_name}' (ID {project_id})...")
            issues = redmine.issue.filter(project_id=project_id, status_id='*', limit=1500)
            logging.info(f"Found {len(issues)} issues in project: '{project_name}' (ID {project_id}).")
        
            if len(issues) == 1500:
                logging.info("Warning: More than 1500 issues found. Consider paginating the results.")
        
            project[project_name]={"id":project_id,"issues":issues}
        else:
            logging.warning(f"Invalid project ID {project_id} provided.")
            project.pop(project_name,None)
        
        return project

# Define a function to process issues and append them to the appropriate DataFrame
def parse_issue_data(issue) -> dict:
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

def process_general_register(redmine: Redmine, project_dict: dict, df_dict: dict) -> None:
    """
    Processes the 'Cadastro-Instrumentos' project by fetching its issues and appending them to the appropriate DataFrame.

    :param redmine: Redmine object connected to the server.
    :param project_dict: Dictionary of project names and their IDs.
    :param df_dict: Dictionary of DataFrames for different trackers.
    """
    try:
        id_cadastro_instrumentos = project_dict[PRJ_INSTR_GENERAL_REGISTER]
        project_dict.pop(PRJ_INSTR_GENERAL_REGISTER, None)
    
        # Fetch issues for 'Instrumentos' project
        cadastro_instrumentos = {PRJ_INSTR_GENERAL_REGISTER: id_cadastro_instrumentos}
        cadastro_instrumentos = fetch_issues_by_project(redmine, cadastro_instrumentos)
    
        # Get the issues for 'Cadastro-Instrumentos'
        issues_cadastro_instrumentos = cadastro_instrumentos[PRJ_INSTR_GENERAL_REGISTER]["issues"]

        # Process each issue and store it in the appropriate DataFrame
        for issue in issues_cadastro_instrumentos:
            issue_data = parse_issue_data(issue)
            try:
                # Append the issue data to the appropriate DataFrame
                df_dict[issue.tracker.name] = pd.concat([df_dict[issue.tracker.name],
                                                            pd.DataFrame([issue_data])],
                                                        ignore_index=True)
            except KeyError:
                logging.warning(f"Tracker '{issue.tracker.name}' not found in DataFrame dictionary. Skipping issue ID {issue.id}.")
                            
    except KeyError:
        logging.error(f"Project '{PRJ_INSTR_GENERAL_REGISTER}' not found in the fetched projects.")
        return

def main():
    # initialize logging
    formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    # Initialize DataFrames for different trackers
    df_dict:dict = {"Categoria de instrumento": pd.DataFrame(),
                    "Tipo de instrumento": pd.DataFrame(),
                    "Marca e Modelo": pd.DataFrame(),
                    "Tipo de Acessório": pd.DataFrame()}
    
    # Ask for Redmine URL and user credentials
    print("\nWelcome to the Fiscaliza Instrument Extraction Tool!\n")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ").strip()

    try:
        # Connect to Redmine
        redmine = Redmine(REDMINE_URL, username=username, password=password)

        # Query for existing projects
        logging.info("Fetching projects...")
        projects = redmine.project.all()
        project_dict = {project.name: project.id for project in projects if "Instrumentos" in project.name}
        
        # Check projects were found
        if project_dict:
            logging.info(f"Found {len(project_dict)-1} projects matching criteria.")
        else:
            logging.warning("Project with keyword 'Instrumentos' not found.")
        
        process_general_register(redmine, project_dict, df_dict)
        
        # Fetch issues for other projects
        equipment_issues = fetch_issues_by_project(redmine, project_dict)
        
        for project_name, project in equipment_issues.items():
            issues = project["issues"]
            logging.info(f"Processing issues for project: '{project_name}' (ID {project['id']})...")
            
            # Process each issue and store it in the appropriate DataFrame
            for issue in issues:
                parse_issue_data(issue)

    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()