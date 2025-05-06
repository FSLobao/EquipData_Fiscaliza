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

# Constants
REDMINE_URL = "https://sistemas.anatel.gov.br/fiscaliza"
PRJ_CADASTRO_DE_INSTRUMENTOS="Cadastro-Instrumentos"
PRJ_REDE_DE_MONITORAMENTO="Rede de Monitoramento Remoto do Espectro"

# Global variable to store the Redmine connection
redmine: Redmine = None

def fetch_issues_by_project_id(project_id: int) -> list:
    """
    Fetches issues for a given project ID from the Redmine server.

    Args:
    project_id (int): The ID of the project to fetch issues for.

    Returns:
    list: A list of issues for the specified project.
    """
    if project_id:
        logging.info(f"Fetching issues for project (ID: {project_id})...")
        issues = redmine.issue.filter(project_id=project_id, status_id='*')
        logging.info(f"Found {len(issues)} issues in project with ID {project_id}.")
    
        if len(issues) == 1000:
            logging.info(f"Warning: More than 1000 issues found. Consider paginating the results.")
    
        return issues
    else:
        logging.warning("Invalid project ID provided.")
        return []


def main():
    # initialize logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Ask for Redmine URL and user credentials
    username = input("Enter your Redmine username: ").strip()
    password = getpass.getpass("Enter your Redmine password: ").strip()

    try:
        # Connect to Redmine
        redmine = Redmine(REDMINE_URL, username=username, password=password)

        # Query for existing projects
        logging.info("\nFetching projects...")
        projects = redmine.project.all()

        # Create a dictionary with project names as keys and IDs as values, where the project name contains "Instrumentos" or "Rede de Monitoramento"
        project_dict = {project.name: project.id for project in projects if "Instrumentos" in project.name}
        
        # Check projects were found
        if project_dict:
            logging.info(f"Found {len(project_dict)} projects matching criteria.")
        else:
            logging.warning("Project 'Instrumentos' not found.")

        id_cadastro_instrumentos = project_dict.get(PRJ_CADASTRO_DE_INSTRUMENTOS, None)
        project_dict.pop(PRJ_CADASTRO_DE_INSTRUMENTOS, None)
        
        # Fetch issues for 'Instrumentos' project
        issues_cadastro_instrumentos = fetch_issues_by_project_id(id_cadastro_instrumentos)
        
        if issues_cadastro_instrumentos:
            logging.info(f"Found {len(issues_cadastro_instrumentos)} issues in project '{PRJ_CADASTRO_DE_INSTRUMENTOS}'.")
        else:
            logging.warning(f"No issues found in project '{PRJ_CADASTRO_DE_INSTRUMENTOS}'.")
        
        

    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()