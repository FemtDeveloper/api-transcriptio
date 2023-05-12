import re
from dotenv import load_dotenv
import openai
import datetime
import glob
from time import time, sleep

load_dotenv()
from supabase import create_client, Client

import os


url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
openai.api_key = os.environ.get("OPEN_API_KEY")


def delete_previous_files(directory):
    files = glob.glob(f"{directory}/*")
    for file in files:
        os.remove(file)


def open_file(filepath):
    with open(filepath, "r", encoding="utf-8") as infile:
        return infile.read()


def gpt3_embedding(content, engine="text-embedding-ada-002"):
    content = content.encode(
        encoding="ASCII", errors="ignore"
    ).decode()  # fix any UNICODE errors
    response = openai.Embedding.create(input=content, engine=engine)
    vector = response["data"][0]["embedding"]  # this is a normal list
    return vector


def timestamp_to_datetime(unix_time):
    return datetime.datetime.fromtimestamp(unix_time).strftime(
        "%A, %B %d, %Y at %I:%M%p %Z"
    )


def load_conversation(results):
    ids = [m.get("id") for m in results["matches"] if "id" in m]
    print(ids)
    if ids:
        ids_string = ",".join(
            ids
        )  # Convert the list of UUIDs to a comma-separated string
        response = (
            supabase.table("messages_metadata")
            .select("message, timestring")
            .filter("uuid", "in", f"({ids_string})")  # Pass the UUIDs as a string
            .order("timestring")
            .execute()
        )
        rows = response.data if response.data else []
        ordered_messages = [row["message"] for row in rows]
        return "\n".join(ordered_messages).strip()

    return "no hay ids"


def save_file(filepath, content):
    with open(filepath, "w", encoding="utf-8") as outfile:
        outfile.write(content)


def gpt3_completion(
    prompt,
    engine="text-davinci-003",
    temp=0.0,
    top_p=1.0,
    tokens=400,
    freq_pen=0.0,
    pres_pen=0.0,
    stop=["USER:", "RAVEN:"],
):
    max_retry = 5
    retry = 0
    prompt = prompt.encode(encoding="ASCII", errors="ignore").decode()
    while True:
        try:
            response = openai.Completion.create(
                engine=engine,
                prompt=prompt,
                temperature=temp,
                max_tokens=tokens,
                top_p=top_p,
                frequency_penalty=freq_pen,
                presence_penalty=pres_pen,
                stop=stop,
            )
            text = response["choices"][0]["text"].strip()
            text = re.sub("[\r\n]+", "\n", text)
            text = re.sub("[\t ]+", " ", text)
            filename = "%s_gpt3.txt" % time()
            if not os.path.exists("gpt3_logs"):
                os.makedirs("gpt3_logs")
            save_file("gpt3_logs/%s" % filename, prompt + "\n\n==========\n\n" + text)
            return text
        except Exception as oops:
            retry += 1
            if retry >= max_retry:
                return "GPT3 error: %s" % oops
            print("Error communicating with OpenAI:", oops)
            sleep(1)
