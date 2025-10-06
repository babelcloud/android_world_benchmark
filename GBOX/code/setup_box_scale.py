"""Setup script to rescale the Android box UI actions."""

import os
from gbox_sdk import GboxSDK


def main():
    # Box ID from simple_claude_agent.py
    box_id = "your_gbox_id"

    # Initialize GboxSDK
    gbox_sdk = GboxSDK(api_key=os.environ["GBOX_API_KEY"])

    # Get the box
    box = gbox_sdk.get(box_id)

    # Update UI Action setting (scale)
    updated = box.action.update_settings(scale=0.8)

    print(f"✅ Updated box {box_id} scale setting: {updated}")


if __name__ == "__main__":
    main()
