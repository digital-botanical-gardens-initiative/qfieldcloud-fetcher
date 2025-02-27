#!/bin/bash

# To obtain the actual path to repo folder
p=$(dirname $(dirname $(realpath $0)))

# .env path
env_path="${p}/.env"

# Load the .env file
source "${env_path}"

# Get scripts folder
scripts_folder="${p}/qfieldcloud_fetcher/"

# Run a script and check its return code
run_script() {
    script_name=$1
    echo "Running $script_name"
    # Redirect all output to the log file
    exec &>> "$LOGS_FOLDER/$script_name.log"
    python3 "${scripts_folder}${script_name}.py"
    if [ $? -ne 0 ]; then
        echo "$script_name failed"
        exit 1
    fi
}

# Run fetcher
run_script "fetcher"

# Run csv generation
#run_script "csv_generator"

# Run csv formatter
#run_script "csv_formatter"

# Run create directus fields
#run_script "fields_creator"

# Run db updater
#run_script "db_updater"

# Run directus link maker
#run_script "directus_link_maker"

# Run pictures renamer
#run_script "pictures_renamer"
