#!/bin/bash

gcloud compute scp --recurse nemde-backtest-p:~/nemde/reports/*.zip ~/Desktop/repos/projects/nemde-dev/nemde/reports/
gcloud compute scp --recurse nemde-backtest-p:~/nemde/reports/latest.xml ~/Desktop/repos/projects/nemde-dev/nemde/reports/latest.xml