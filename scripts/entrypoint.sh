#!/bin/bash

echo "Sleeping for 10s" && sleep 10
echo "Starting run"

# Initialise database tables
/usr/bin/python3.9 /app/scripts/initialise_tables.py

# Upload casefiles
/usr/bin/python3.9 /app/scripts/upload_casefiles.py

# Prepare a new test run
if [ $NEW_RUN -eq 1 ]
then
    echo "Preparing new run"
    pytest -m prepare_new_test_run -n 1
fi

# Run model validation tests
pytest --verbose --capture=tee-sys --junitxml=/app/reports/latest.xml -n $N_WORKERS -m "not prepare_new_test_run"
status=$?

# Save junitxml report to database. Exit if pytest exit status is unexpected.
[ $status -ne 0 ] && [ $status -ne 1 ] && echo "Unexpected error status" && exit 1

/usr/bin/python3.9 /app/scripts/save_junitxml_to_db.py

# Construct reports - instance may need > 40GB of RAM if constructing monthly report
# /usr/bin/python3.9 /app/scripts/create_reports.py

echo "Finished run"

tail -f /dev/null