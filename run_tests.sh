#!/bin/bash

timestamp=$(date +"%Y%m%d%H%M%S")
filename=~/logs/execution-$timestamp.log

mkdir -p ~/logs
sudo nohup docker-compose -f docker-compose.yml up --build > $filename &