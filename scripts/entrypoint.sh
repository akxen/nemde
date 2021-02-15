#!/bin/bash

# Initialise database tables
/usr/bin/python3.9 /app/scripts/initialise_tables.py

# Upload casefiles
/usr/bin/python3.9 /app/scripts/upload_casefiles.py

# Prepare a new test run - comment out if want to continue previous run
pytest -m prepare_new_test_run -n 1

# Run model validation tests
pytest --verbose --capture=tee-sys --junitxml=/app/nemde/tests/report.xml -n 3 -m validate
status=$?

# Save junitxml report to database. Exit is pytest exit status is unexpected
[ $status -ne 0 ] && [ $status -ne 1 ] && echo "Unexpected error status" && exit 1

/usr/bin/python3.9 /app/scripts/save_junitxml_to_db.py

# Construct reports
/usr/bin/python3.9 /app/scripts/create_reports.py

tail -f /dev/null