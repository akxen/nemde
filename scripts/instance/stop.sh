#!/bin/bash

source config.sh
gcloud compute instances stop $INSTANCE --zone=$ZONE

