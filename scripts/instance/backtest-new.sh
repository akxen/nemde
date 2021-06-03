#!/bin/bash

source config.sh
gcloud compute ssh $INSTANCE --zone=$ZONE --command="(cd nemde && chmod +x run_tests.sh && sed -i -e 's/NEW_RUN=0/NEW_RUN=1/' config/default.env && ./run_tests.sh)"
