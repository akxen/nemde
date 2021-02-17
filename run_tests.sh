#!/bin/bash

sudo nohup docker-compose -f docker-compose.yml up --build > ~/execution.log &