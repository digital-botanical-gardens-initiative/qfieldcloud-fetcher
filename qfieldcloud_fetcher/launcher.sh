#!/bin/bash

# To obtain the actual path to inat_fetcher dir
p=$(dirname $(dirname $(realpath $0)))

scripts_folder="/src/"
path_to_scripts="${p}${scripts_folder}"

# Function to run a script and check its return code
run_script() {
    script_name=$1
    echo "Running $script_name"
    python3 "${path_to_scripts}${script_name}.py"
    if [ $? -ne 0 ]; then
        echo "$script_name failed"
        exit 1
    fi
}

# Run fetcher
run_script "fetcher"

# Uncomment the following lines to run the scripts as needed
# Run location formatter
# run_script "location_formatter"

# Run emi id extracter
run_script "emi_id_extracter"

# Run create directus fields
run_script "create_directus_fields"

# Run db updater
run_script "db_updater"

# Run directus link maker
run_script "directus_link_maker"
