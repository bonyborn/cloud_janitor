import boto3
import json
import argparse
import time
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

# how many days a volume should be idle before cleanup
IDLE_DAYS = 7
# retries for API calls
MAX_RETRIES = 3
# wait time between retries
RETRY_DELAY = 2

def get_unattached_volumes(ec2_client):
    """Return a list of all unattached EBS volumes"""
    volumes = []
    try:
        paginator = ec2_client.get_paginator('describe_volumes')
        for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
            volumes += page.get("Volumes", [])
    except ClientError as e:
        print("Could not fetch volumes:", e)
    return volumes

def is_volume_old(volume):
    """Check if volume has been idle longer than IDLE_DAYS"""
    try:
        create_time = volume["CreateTime"]
        age = datetime.now(timezone.utc) - create_time
        return age > timedelta(days=IDLE_DAYS)
    except KeyError:
        return False

def delete_volume_safe(ec2_client, volume_id, dry_run):
    """Delete a volume safely with retries"""
    if dry_run:
        print(f"[DRY-RUN] Would delete {volume_id}")
        return
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ec2_client.delete_volume(VolumeId=volume_id)
            print(f"Deleted {volume_id}")
            return
        except ClientError as e:
            print(f"Error deleting {volume_id} (try {attempt}): {e}")
            time.sleep(RETRY_DELAY)
    print(f"Failed to delete {volume_id} after {MAX_RETRIES} attempts")

def main(dry_run):
    ec2 = boto3.client("ec2")
    log_results = []

    print("Fetching unattached volumes...")
    volumes = get_unattached_volumes(ec2)

    if not volumes:
        print("No unattached volumes found.")
        return

    for vol in volumes:
        if is_volume_old(vol):
            info = {
                "VolumeId": vol.get("VolumeId", "Unknown"),
                "SizeGB": vol.get("Size", "Unknown"),
                "Created": vol.get("CreateTime", "Unknown").isoformat() if vol.get("CreateTime") else "Unknown"
            }
            log_results.append(info)
            print("Found idle volume:", info)

            delete_volume_safe(ec2, vol.get("VolumeId"), dry_run)

    # save log
    try:
        with open("cleanup_log.json", "w") as f:
            json.dump(log_results, f, indent=2)
        print("Saved cleanup log to cleanup_log.json")
    except Exception as e:
        print("Could not save log:", e)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up unattached EBS volumes")
    parser.add_argument("--dry-run", action="store_true", help="Just list volumes, don't delete")
    args = parser.parse_args()
    main(args.dry_run)
