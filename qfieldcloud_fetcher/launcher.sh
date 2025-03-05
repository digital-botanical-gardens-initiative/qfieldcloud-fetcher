#!/bin/bash


# Add a comment

# To obtain the actual path to repo folder
p=$(dirname $(dirname $(realpath $0)))

# .env path
env_path="${p}/.env"

# Load the .env file
source "${env_path}"

# Clean input gpkg and csv to keep only up-to-date data
rm -rf "${DATA_PATH}/in/gpkg"
rm -rf "${DATA_PATH}/raw_csv"
rm -rf "${DATA_PATH}/formatted_csv"

# Clean logs folder if the used space is greater than 100MB
SIZE_LIMIT_MB=100

# Get the folder size in MB
FOLDER_SIZE_MB=$(du -sm "$LOGS_PATH" | awk '{print $1}')

# Check if the folder size exceeds the limit
if [ "$FOLDER_SIZE_MB" -gt "$SIZE_LIMIT_MB" ]; then
    echo "Folder size ($FOLDER_SIZE_MB MB) exceeds the limit ($SIZE_LIMIT_MB MB). Deleting contents..."

    # Delete all contents of the folder
    rm -rf "${LOGS_PATH}/*"

    echo "Contents of the folder have been deleted."
fi

# Create folders
mkdir -p "${DATA_PATH}"
mkdir -p "${LOGS_PATH}"

# Get scripts folder
scripts_folder="${p}/qfieldcloud_fetcher/"

# Run a script and check its return code
run_script() {
    script_name=$1
    # Redirect all output to the log file
    exec &>> "$LOGS_PATH/$script_name.log"
    echo "Running $script_name"
    poetry run python3 "${scripts_folder}${script_name}.py"
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

# Run pictures resizer
run_script "pictures_resizer"
