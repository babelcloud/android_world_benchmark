import os
from dotenv import load_dotenv
from gbox_sdk import GboxSDK

# Load environment variables from .env file
load_dotenv()

def main():
    api_key = os.getenv("GBOX_API_KEY")
    gbox = GboxSDK(api_key=api_key)

    box = gbox.create(
        type="android",
        config={
            "deviceType": "physical",
            "labels":{
                "gbox.ai/device-id": "EMULATOR36X1X9X0-usb" # Replace with your device ID
            }
        }
    )

    print(f"Android box created: {box.data.id}")

    live_view = box.live_view()

    print(f"Live view URL: {live_view.url}")

if __name__ == "__main__":
    main()