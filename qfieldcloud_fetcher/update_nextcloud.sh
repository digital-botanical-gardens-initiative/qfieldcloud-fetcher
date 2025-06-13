#!/bin/bash

# To obtain the actual path to repo folder
p=$(dirname $(dirname $(realpath $0)))

# .env path
env_path="${p}/.env"

# Load the .env file
source "${env_path}"

exec &>> "$LOGS_PATH/update_nextcloud.log"
echo "Running update_nextcloud.sh"

docker exec -u www-data -it 2fffa94f2016 php occ files:scan --all
