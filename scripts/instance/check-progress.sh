#!/bin/bash

source config.sh
gcloud compute ssh $INSTANCE --zone=$ZONE --command="sudo docker exec nemde_mysql_1 sh -c \"echo 'SELECT COUNT(*) FROM nemde.results WHERE group_id=(SELECT group_id FROM nemde.results ORDER BY row_id DESC LIMIT 1);' > check_progress.sql ; mysql -p$MYSQL_PASSWORD < check_progress.sql\""
