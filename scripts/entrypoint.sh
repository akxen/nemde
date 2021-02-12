#!/bin/bash

# tail -f /dev/null

# Run tests
pytest --verbose --capture=tee-sys --junitxml=/app/nemde/tests/report.xml
status=$?

# Save junitxml report to database. Exit is pytest exist status is unexpected.
[ $status -ne 0 ] && [ $status -ne 1 ] && echo "Unexpected error status" && exit 1

/usr/bin/python3.9 /app/scripts/save_junitxml_to_db.py

# Construct reports
/usr/bin/python3.9 /app/scripts/create_reports.py