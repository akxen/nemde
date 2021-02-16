#!/bin/bash

sudo nohup docker-compose -f docker-compose-offline.yml up --build > ~/execution.log &