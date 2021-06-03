#!/bin/bash

source config.sh
gcloud compute ssh $INSTANCE --zone=$ZONE

