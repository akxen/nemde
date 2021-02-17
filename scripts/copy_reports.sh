#!/bin/bash

gcloud compute scp --recurse vm-4-p:~/nemde/reports/*.zip ~/Desktop/repos/projects/nemde-dev/nemde/reports/
gcloud compute scp --recurse vm-4-p:~/nemde/reports/latest.xml ~/Desktop/repos/projects/nemde-dev/nemde/reports/latest.xml