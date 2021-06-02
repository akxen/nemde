#!/bin/bash

gcloud compute scp --recurse nemde-backtest-p:~/nemde/reports/*.zip ~/Desktop/repos/projects/nemde-dev/nemde/reports/ --zone=asia-east1-b
gcloud compute scp --recurse nemde-backtest-p:~/nemde/reports/latest.xml ~/Desktop/repos/projects/nemde-dev/nemde/reports/latest.xml --zone=asia-east1-b