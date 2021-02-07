#!/bin/bash

set -e

# Run tests
pytest --verbose --capture=tee-sys --junitxml=/app/nemde/tests/report.xml 

# Save junitxml report to database
/usr/bin/python3.9 /app/scripts/save_junitxml_to_db.py

# Construct reports
/usr/bin/python3.9 /app/scripts/reports.py