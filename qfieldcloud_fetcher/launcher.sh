#!/bin/bash

# To obtain the actual path to qfieldcloud_fetcher dir
p=$(dirname $(dirname $(realpath $0)))

scripts_folder="/qfieldcloud_fetcher/"
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

# Run csv generation
run_script "csv_generator"

# Run csv formatter
run_script "csv_formatter"

# Run create directus fields
run_script "fields_creator"

# Run db updater
run_script "db_updater"

# Run directus link maker
run_script "directus_link_maker"

# Run pictures renamer
run_script "pictures_renamer"
