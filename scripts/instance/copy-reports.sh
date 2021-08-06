#!/bin/bash

source config.sh
gcloud compute scp --recurse $INSTANCE:~/nemde/reports/*.zip $REPORTS_DIR/ --zone=$ZONE
gcloud compute scp --recurse $INSTANCE:~/nemde/reports/latest.xml $REPORTS_DIR/latest.xml --zone=$ZONE