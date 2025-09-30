from gbox_sdk import GboxSDK
import asyncio


async def main():
    try:
        gbox = GboxSDK(
            api_key="gbox_5qHk4HzasE9QCk7qm0kCwHulCSfZ5FnyKgspculb9HGdzd1HY3",
            base_url="http://gbox.localhost:2080/api/v1",
        )
        # Initialize Android box (default lifecycle: 5 minutes, will be automatically released after 5 minutes)
        print("Initializing android box...")
        my_android_box = await gbox.create(
            type="android",
            config={"expires_in": "5m"}
        )
        print("Device created:", my_android_box.id)
        return my_android_box
    except Exception as e:
        print(f"Error creating Android box: {e}")
        return None


if __name__ == "__main__":
    asyncio.run(main())