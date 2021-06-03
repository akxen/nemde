#!/bin/bash

source config.sh
gcloud compute scp --recurse $INSTANCE:~/nemde/reports/*.zip ~/Desktop/repos/projects/nemde-dev/nemde/reports/ --zone=$ZONE
gcloud compute scp --recurse $INSTANCE:~/nemde/reports/latest.xml ~/Desktop/repos/projects/nemde-dev/nemde/reports/latest.xml --zone=$ZONE