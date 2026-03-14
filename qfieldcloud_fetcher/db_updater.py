import argparse
import math
import os
import typing
from dataclasses import dataclass
from urllib.parse import urlencode

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# Access the environment variables
directus_instance = os.getenv("DIRECTUS_INSTANCE")
directus_email = os.getenv("DIRECTUS_USERNAME")
directus_password = os.getenv("DIRECTUS_PASSWORD")
data_path = os.getenv("DATA_PATH")

# Construct folders paths
out_csv_path = f"{data_path}/formatted_csv"


@dataclass
class PreparedObservation:
    sample_code: str
    project: str
    filename: str
    observation: dict[str, typing.Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create new observations from formatted CSVs in Directus.")
    parser.add_argument("--project", default=None, help="Only process a single project folder by name.")
    parser.add_argument("--progress-every", type=int, default=100, help="Print progress every N rows.")
    parser.add_argument(
        "--allow-existing-sample-id-overwrite",
        action="store_true",
        help="Update an existing Directus record when sample_id already exists. Intended for testing only.",
    )
    return parser.parse_args()


def sanitize_value(value: typing.Any) -> typing.Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None if math.isnan(value) else float(value)
    return value


def build_observation(obs: dict[str, typing.Any], project: str) -> dict[str, typing.Any]:
    observation: dict[str, typing.Any] = {}
    for column, value in obs.items():
        clean_column = column.replace(".", "_").replace("(", "").replace(")", "")
        if column == "geometry":
            latitude = obs.get("latitude")
            longitude = obs.get("longitude")
            if latitude is not None and longitude is not None:
                observation["geometry"] = {
                    "type": "Point",
                    "coordinates": [latitude, longitude],
                }
            else:
                observation["geometry"] = None
            continue
        observation[clean_column] = sanitize_value(value)

    observation["qfield_project"] = project
    return observation


def collect_observations(args: argparse.Namespace) -> list[PreparedObservation]:
    prepared: list[PreparedObservation] = []
    seen_sample_ids: dict[str, tuple[str, str]] = {}
    file_count = 0

    for root, _dirs, files in os.walk(out_csv_path):
        project = os.path.basename(root)
        if args.project and project != args.project:
            continue

        for filename in files:
            if not filename.endswith(".csv") or filename == "SBL_20004_2022_EPSG:4326.csv":
                continue

            file_count += 1
            constructed_path = root + "/" + filename
            df = pd.read_csv(constructed_path)

            if df.empty:
                continue

            total_rows = len(df)
            print(f"Preparing {constructed_path} (rows={total_rows})")
            project = root.split("/")[-1]
            df["qfield_project"] = project

            for i in range(len(df)):
                if args.progress_every > 0 and i > 0 and i % args.progress_every == 0:
                    print(f"Progress {constructed_path}: {i}/{total_rows}")

                obs = df.iloc[i].to_dict()
                sample_code = obs.get("sample_id")
                if sample_code is None or (isinstance(sample_code, float) and math.isnan(sample_code)):
                    print(f"sample_id null for project {project}, file {filename}, row={i + 1}")
                    continue

                sample_code = str(sample_code).strip()
                if not sample_code:
                    print(f"sample_id empty for project {project}, file {filename}, row={i + 1}")
                    continue

                if sample_code in seen_sample_ids:
                    first_project, first_file = seen_sample_ids[sample_code]
                    raise SystemExit(
                        "Duplicate sample_id found in input CSVs before any Directus write:\n"
                        f"sample_id={sample_code}\n"
                        f"first_seen={first_project}/{first_file}\n"
                        f"duplicate={project}/{filename}\n"
                        "Fix the source data before retrying."
                    )
                seen_sample_ids[sample_code] = (project, filename)

                prepared.append(
                    PreparedObservation(
                        sample_code=sample_code,
                        project=project,
                        filename=filename,
                        observation=build_observation(obs, project),
                    )
                )

    print(f"Preparation finished. Files processed: {file_count}, observations prepared: {len(prepared)}")
    return prepared


def find_existing_sample_ids(
    session: requests.Session,
    headers: dict[str, str],
    directus_api: str,
    sample_codes: list[str],
) -> dict[str, dict[str, typing.Any]]:
    collisions: dict[str, dict[str, typing.Any]] = {}
    for sample_code in sample_codes:
        params = {
            "filter[sample_id][_eq]": sample_code,
            "fields": "id,sample_id,qfield_project,date_created,date_updated",
            "limit": 1,
        }
        response_get = session.get(url=directus_api, headers=headers, params=params)
        if response_get.status_code != 200:
            raise SystemExit(f"Error checking existing sample_id {sample_code}: {response_get.status_code} - {response_get.text}")
        data = response_get.json().get("data", [])
        if data:
            collisions[sample_code] = data[0]
    return collisions


def main() -> None:
    args = parse_args()
    if args.project:
        print(f"Filtering to project: {args.project}")
    if args.allow_existing_sample_id_overwrite:
        print("Existing sample_id overwrite enabled for this run.")

    prepared = collect_observations(args)
    if not prepared:
        print("No observations to import.")
        return

    # Create a session object for making requests
    session = requests.Session()

    # Send a POST request to the login endpoint
    directus_login = f"{directus_instance}/auth/login"
    response = session.post(directus_login, json={"email": directus_email, "password": directus_password})

    # Test if connection is successful
    if response.status_code != 200:
        print("Connection to Directus failed")
        print(f"Error: {response.status_code} - {response.text}")
        raise SystemExit(1)

    print("Connection to Directus successful")

    # Construct the API endpoint
    collection_name = "Field_Data"
    directus_api = f"{directus_instance}/items/{collection_name}/"

    # Stores the access token
    data = response.json()["data"]
    directus_token = data["access_token"]

    # Construct headers with authentication token
    headers = {
        "Authorization": f"Bearer {directus_token}",
        "Content-Type": "application/json",
    }

    collisions = find_existing_sample_ids(
        session=session,
        headers=headers,
        directus_api=directus_api,
        sample_codes=[item.sample_code for item in prepared],
    )
    if collisions:
        if not args.allow_existing_sample_id_overwrite:
            print("FATAL: existing sample_id collision(s) detected in Directus. No records were written.")
            for collision in list(collisions.values())[:20]:
                sample_id = collision.get("sample_id")
                query = urlencode({"filter[sample_id][_eq]": sample_id})
                print(
                    " - "
                    f"sample_id={sample_id}, "
                    f"directus_id={collision.get('id')}, "
                    f"qfield_project={collision.get('qfield_project')}, "
                    f"date_created={collision.get('date_created')}, "
                    f"date_updated={collision.get('date_updated')}, "
                    f"url={directus_api}?{query}"
                )
            if len(collisions) > 20:
                print(f" ... and {len(collisions) - 20} more collision(s)")
            raise SystemExit(1)

        print("WARNING: existing sample_id collision(s) detected in Directus. Updating those records because overwrite is enabled.")
        for collision in list(collisions.values())[:20]:
            sample_id = collision.get("sample_id")
            query = urlencode({"filter[sample_id][_eq]": sample_id})
            print(
                " - "
                f"sample_id={sample_id}, "
                f"directus_id={collision.get('id')}, "
                f"qfield_project={collision.get('qfield_project')}, "
                f"date_created={collision.get('date_created')}, "
                f"date_updated={collision.get('date_updated')}, "
                f"url={directus_api}?{query}"
            )
        if len(collisions) > 20:
            print(f" ... and {len(collisions) - 20} more collision(s)")

    created = 0
    updated = 0
    for item in prepared:
        collision = collisions.get(item.sample_code)
        if collision is not None:
            directus_patch = f"{directus_api}{collision['id']}"
            response_patch = session.patch(url=directus_patch, headers=headers, json=item.observation)
            if response_patch.status_code not in (200, 204):
                print(
                    f"Error patching observation with id {item.sample_code}, project {item.project}, file {item.filename}: "
                    f"{response_patch.status_code} - {response_patch.text}"
                )
                raise SystemExit(1)
            updated += 1
            continue

        response_post = session.post(url=directus_api, headers=headers, json=item.observation)
        if response_post.status_code not in (200, 201):
            print(
                f"Error posting observation with id {item.sample_code}, project {item.project}, file {item.filename}: "
                f"{response_post.status_code} - {response_post.text}"
            )
            raise SystemExit(1)
        created += 1

    print(f"Import finished. New Directus records created: {created}, updated: {updated}")


if __name__ == "__main__":
    main()
