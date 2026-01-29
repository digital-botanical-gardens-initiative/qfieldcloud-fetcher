# qfieldcloud-fetcher

[![Release](https://img.shields.io/github/v/release/digital-botanical-gardens-initiative/qfieldcloud-fetcher)](https://img.shields.io/github/v/release/digital-botanical-gardens-initiative/qfieldcloud-fetcher)
[![Build status](https://img.shields.io/github/actions/workflow/status/digital-botanical-gardens-initiative/qfieldcloud-fetcher/main.yml?branch=main)](https://github.com/digital-botanical-gardens-initiative/qfieldcloud-fetcher/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/digital-botanical-gardens-initiative/qfieldcloud-fetcher/branch/main/graph/badge.svg)](https://codecov.io/gh/digital-botanical-gardens-initiative/qfieldcloud-fetcher)
[![Commit activity](https://img.shields.io/github/commit-activity/m/digital-botanical-gardens-initiative/qfieldcloud-fetcher)](https://img.shields.io/github/commit-activity/m/digital-botanical-gardens-initiative/qfieldcloud-fetcher)
[![License](https://img.shields.io/github/license/digital-botanical-gardens-initiative/qfieldcloud-fetcher)](https://img.shields.io/github/license/digital-botanical-gardens-initiative/qfieldcloud-fetcher)

A python project to fetch data from a QFieldCloud instance, prepare pictures for iNaturalist import and add data to NextCloud.

- **Github repository**: <https://github.com/digital-botanical-gardens-initiative/qfieldcloud-fetcher/>

## Prerequisites

Having a self-hosted instance of QFieldCloud or having an account on the offical instance of QFieldCloud. To create a QFieldCloud self-hosted instance see https://github.com/digital-botanical-gardens-initiative/QFieldCloud/

Having a self-hosted instance of Directus or having an account on the official instance of Directus. To create a Directus self-hosted instance see https://github.com/digital-botanical-gardens-initiative/Directus-prod/

Having a self-hosted instance of NextCloud. To create a NextCloud self-hosted instance see https://github.com/digital-botanical-gardens-initiative/NextCloud/

## Setup

### 1. Clone the repository to your local machine:

```bash
git clone https://github.com/digital-botanical-gardens-initiative/qfieldcloud-fetcher.git
cd qfieldcloud-fetcher
```

### 2. Create a .env file in the root folder and edit it to suit your needs:

```bash
cp .env.example .env
vim .env
```

### 3. set up an environment with `poetry`:

```bash
poetry install
```

Then activate the environment:

```bash
poetry shell
```

and run the `main.py` script:

```bash
python main.py
```

If you do not have poetry, you can install it with the command:

```bash
pipx install poetry
```

### 4. Run launcher.sh script in cronjob:

- Add the user that will run the cronjob to NextCloud data group (Permits it to access NextCloud data folder):

```sh
sudo usermod -aG www-data your_user
```

- Create a folder in NextCloud web interface

- Locate your newly created folder and allow group write access to it:

```sh
sudo chmod -R g+w /path/to/your/newly/created/folder
```

- Open cronjobs file:

```sh
crontab -e
```

- Add cronjob:

For example to run the fetcher every 2 hours:

```sh
0 */2 * * * /path/to/fetcher/launcher.sh
```

## Fetcher default mode

By default the launcher runs the fetcher in interactive mode so you can choose projects before downloading.
You can change this by setting `FETCHER_DEFAULT_MODE` in your `.env`:

```sh
# .env
FETCHER_DEFAULT_MODE=interactive  # or: dry-run
```

When set to `dry-run`, the launcher will show the plan and exit before downloading.

## Pipeline project filter

If you want the downstream steps (CSV generation, Directus updates, picture processing, etc.) to run
only for a single project, set `PIPELINE_PROJECT` in your `.env`:

```sh
# .env
PIPELINE_PROJECT=jbb
```

The launcher will pass `--project jbb` to all downstream scripts.

## Fetcher usage (CLI)

You can run the fetcher directly when you want precise control over what happens.
The main arguments are:

- `--interactive`: Show a menu to select projects (recommended for manual runs).
- `--dry-run`: Preview what would be downloaded without doing any downloads.
- `--project <name>`: Fetch a single project by its exact name.
- `--mode <incremental|all>`: `incremental` (default) fetches only changed projects; `all` ignores the state and fetches everything.
- `--state-file <path>`: Override the state file location (defaults to `DATA_PATH/state.json`).
- `--manifest-file <path>`: Override the queued deletes manifest (defaults to `DATA_PATH/pending_remote_deletes.json`).
- `--clean-pictures`: Also wipe local pictures for selected projects before fetching.

Examples:

```sh
# Interactive menu
poetry run python3 qfieldcloud_fetcher/fetcher.py --interactive

# Dry-run only
poetry run python3 qfieldcloud_fetcher/fetcher.py --dry-run

# Fetch a specific project (exact name match)
poetry run python3 qfieldcloud_fetcher/fetcher.py --project jbb

# Fetch all projects regardless of state
poetry run python3 qfieldcloud_fetcher/fetcher.py --mode all
```

## Contributing

If you would like to contribute to this project or report issues, please follow our contribution guidelines.

## License

see [LICENSE](https://github.com/digital-botanical-gardens-initiative/qfieldcloud-fetcher/blob/main/LICENSE) for details.
