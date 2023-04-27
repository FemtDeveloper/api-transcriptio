import os
import time

AUDIO_FILES_FOLDER = "audio_files"
MAX_AGE_SECONDS = 24 * 60 * 60

def remove_old_files():
    now = time.time()

    for filename in os.listdir(AUDIO_FILES_FOLDER):
        file_path = os.path.join(AUDIO_FILES_FOLDER, filename)

        if os.path.isfile(file_path):
            file_age = now - os.path.getmtime(file_path)

            if file_age > MAX_AGE_SECONDS:
                os.remove(file_path)
                print(f"Removed {file_path}")

if __name__ == "__main__":
    while True:
        remove_old_files()
        time.sleep(60 * 60)  # Run the cleanup every hour
