import tweepy
import psycopg2
from datetime import datetime, UTC, timezone
import time
from deep_translator import GoogleTranslator
import re
from dotenv import load_dotenv
import os
import requests

load_dotenv()


prefixes = [
    "BREAKING:",
    "JUST IN:",
    "UPDATE:",
    "ALERT:",
    "CURRENCY:",
]


try:
    client = tweepy.Client(
        bearer_token=os.getenv("BEARER_TOKEN"),
        consumer_key=os.getenv("CONSUMER_KEY"),
        consumer_secret=os.getenv("CONSUMER_SECRET"),
        access_token=os.getenv("ACCESS_TOKEN"),
        access_token_secret=os.getenv("ACCESS_TOKEN_SECRET")
    )

    auth_v1 = tweepy.OAuth1UserHandler(
        consumer_key=os.getenv("CONSUMER_KEY"),
        consumer_secret=os.getenv("CONSUMER_SECRET"),
        access_token=os.getenv("ACCESS_TOKEN"),
        access_token_secret=os.getenv("ACCESS_TOKEN_SECRET")
    )

    api_v1 = tweepy.API(auth_v1, wait_on_rate_limit=True)

    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

except Exception as e:
    print(f"API not responding {e}.")

try:
    me = client.get_me()
    print(f'Connected with: {me.data.username}')
except tweepy.TooManyRequests:
    print("Too many request.")
    try:
        me = client.get_me()
        print(f'Connected with: {me.data.username}')
    except Exception as e:
        print(f'Error {e}')
        exit()


try:
    cursor = conn.cursor()
    #getting id of user
    user_info = client.get_user(username='spectatorindex')
    user_id_index = user_info.data.id

    tweety = client.get_users_tweets(
        id = user_id_index,
        max_results = 8,
        expansions=["attachments.media_keys"],
        media_fields=["url"]
    )

    media_map = {}
    if "media" in tweety.includes:
        for m in tweety.includes["media"]:
            media_map[m.media_key] = m

    for tweet in tweety.data:
        print("Tweet ID:", tweet.id)
        print("Treść:", tweet.text)
        cursor.execute(
            "SELECT 1 FROM \"Tweets\" WHERE id = %s",
            (tweet.id,)
        )
        odp = cursor.fetchone()
        if odp:
            continue
        else:
            #variables
            last_tweet_id = tweet.id
            last_tweet_text = tweet.text

            last_tweet_text = re.sub(r"https://t\.co/\S+", "", last_tweet_text).strip()

            media_url = None
            if getattr(tweet, "attachments", None) and "media_keys" in tweet.attachments:
                for media_key in tweet.attachments["media_keys"]:
                    if media_key in media_map and media_map[media_key].type == "photo":
                        media_url = media_map[media_key].url
                        break

            #deleting prefixes
            for i in prefixes:
                if last_tweet_text.startswith(i):
                    last_tweet_text = last_tweet_text[len(i):].strip()
            #adding comment to inform that im not the tweet creator (avoiding issues with twitter)
            comment = "Tłumaczenie @spectatorindex."

            #SETTING TRANSLATING LANGUAGE
            last_tweet_translated = GoogleTranslator(source='en',target='pl').translate(last_tweet_text)
            last_tweet_translated = f"{last_tweet_translated}\n\n{comment}"

            day = datetime.now(timezone.utc)
            clock = datetime.now().time()

            #sending info to database
            try:
                image_data = None
                media_id = None
                if media_url:
                    resp = requests.get(media_url)
                    if resp.status_code == 200:
                        image_data = resp.content
                        with open(".venv/temp.jpg", "wb") as f:
                            f.write(image_data)
                        media = api_v1.media_upload("temp.jpg")
                        media_id = media.media_id

                #checking if last_tweet_id already in database
                print(f"Dane do wstawienia: {last_tweet_id}, {last_tweet_text}, {last_tweet_translated}, {clock}, {day}")
                cursor.execute(
                    """INSERT INTO "Tweets" (id, text, translated_text, czas, data_dodania,images) VALUES (%s, %s, %s,      %s, %s,%s) ON CONFLICT (id) DO NOTHING """,
                    (last_tweet_id, last_tweet_text, last_tweet_translated, clock, day,image_data))
                conn.commit()


                if media_id:
                    client.create_tweet(text=last_tweet_translated, media_ids=[media_id])
                else:
                    client.create_tweet(text=last_tweet_translated)





            except Exception as e:
                print(f'Error in adding values to database.{e}')
                conn.rollback()

except Exception as e:
    print(f'{e}')
finally:

    cursor.close()
    conn.close()


#if u want better translation u need to get chatgpt api