#!/bin/bash

source config.sh
gcloud compute instances describe $INSTANCE --zone=$ZONE | grep '^status: ' | awk '{print $2}'