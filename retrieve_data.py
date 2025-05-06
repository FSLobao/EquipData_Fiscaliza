#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 26 10:00:00 2023
@project: Redmine Project Management
@file: retrieve_data.py
@description: This script connects to a Redmine server and retrieves a list of existing projects.
@license: MIT License
@version: 1.0
@maintainer: Your Name
@maintainer_email:
"""
# Import necessary libraries
from redminelib import Redmine
import logging

# Constants
REDMINE_URL = "https://your-redmine-url.com"

def main():
    # Ask for Redmine URL and user credentials
    username = input("Enter your Redmine username: ").strip()
    password = input("Enter your Redmine password: ").strip()

    try:
        # Connect to Redmine
        redmine = Redmine(redmine_url, username=username, password=password)

        # Query for existing projects
        logging.info("\nFetching projects...")
        projects = redmine.project.all()

        # Display the list of projects
        logging.info("\nExisting Projects:")
        for project in projects:
            print(f"- {project.name} (ID: {project.id})")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()