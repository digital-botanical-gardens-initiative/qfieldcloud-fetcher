#!/bin/bash

exec &>> "$LOGS_PATH/update_nextcloud.log"
echo "Running update_nextcloud.sh"

docker exec -u www-data -it 707c618b01c0 php occ files:scan --all
