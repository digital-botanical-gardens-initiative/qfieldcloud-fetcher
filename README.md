# qfieldcloud-fetcher

[![Release](https://img.shields.io/github/v/release/digital-botanical-gardens-initiative/qfieldcloud-fetcher)](https://img.shields.io/github/v/release/digital-botanical-gardens-initiative/qfieldcloud-fetcher)
[![Build status](https://img.shields.io/github/actions/workflow/status/digital-botanical-gardens-initiative/qfieldcloud-fetcher/main.yml?branch=main)](https://github.com/digital-botanical-gardens-initiative/qfieldcloud-fetcher/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/digital-botanical-gardens-initiative/qfieldcloud-fetcher/branch/main/graph/badge.svg)](https://codecov.io/gh/digital-botanical-gardens-initiative/qfieldcloud-fetcher)
[![Commit activity](https://img.shields.io/github/commit-activity/m/digital-botanical-gardens-initiative/qfieldcloud-fetcher)](https://img.shields.io/github/commit-activity/m/digital-botanical-gardens-initiative/qfieldcloud-fetcher)
[![License](https://img.shields.io/github/license/digital-botanical-gardens-initiative/qfieldcloud-fetcher)](https://img.shields.io/github/license/digital-botanical-gardens-initiative/qfieldcloud-fetcher)

A python project to fetch data from a QFieldCloud instance and prepare pictures for iNaturalist import.

- **Github repository**: <https://github.com/digital-botanical-gardens-initiative/qfieldcloud-fetcher/>

## Prerequisites

Having a self-hosted instance of QFieldCloud or having an account on the offical instance of QFieldCloud.

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

- Open cronjobs file:

```sh
crontab -e
```

- Add cronjobs:

For example to run the fetcher every 2 hours: 
```sh
0 */2 * * * /path/to/fetcher/launcher.sh
```

## Contributing

If you would like to contribute to this project or report issues, please follow our contribution guidelines.

## License

see [LICENSE](https://github.com/digital-botanical-gardens-initiative/qfieldcloud-fetcher/blob/main/LICENSE) for details.