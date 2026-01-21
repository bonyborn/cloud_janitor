import boto3
import json
import argparse
from datetime import datetime, timezone, timedelta

IDLE_DAYS = 7

def get_unattached_volumes(ec2):
    response = ec2.describe_volumes(
        Filters=[{"Name": "status", "Values": ["available"]}]
    )
    return response["Volumes"]

def is_old(volume):
    age = datetime.now(timezone.utc) - volume["CreateTime"]
    return age > timedelta(days=IDLE_DAYS)

def main(dry_run):
    ec2 = boto3.client("ec2")
    results = []

    volumes = get_unattached_volumes(ec2)
    for volume in volumes:
        if is_old(volume):
            info = {
                "VolumeId": volume["VolumeId"],
                "SizeGB": volume["Size"],
                "Created": volume["CreateTime"].isoformat()
            }
            results.append(info)
            print("Found:", info)

            if not dry_run:
                ec2.delete_volume(VolumeId=volume["VolumeId"])

    with open("cleanup_log.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(args.dry_run)
