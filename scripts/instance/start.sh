#!/bin/bash

source config.sh

gcloud compute instances set-machine-type $INSTANCE --machine-type=$MACHINE_TYPE --zone=$ZONE
gcloud compute instances start $INSTANCE --zone=$ZONE
