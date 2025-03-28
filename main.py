from typing import Optional
import concurrent.futures
import feedparser
import time
import requests
import json
import urllib.parse
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi import FastAPI

app = FastAPI()
CONSUMER_KEY = os.getenv('CONSUMER_KEY')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
base_url = 'https://getpocket.com/v3/'

# List of RSS feeds to monitor
RSS_FEEDS = [
    'https://rthk9.rthk.hk/rthk/news/rss/c_expressnews_cfinance.xml',
    'https://rthk9.rthk.hk/rthk/news/rss/c_expressnews_clocal.xml',
    'https://www.scmp.com/rss/36/feed',
    'https://www.scmp.com/rss/91/feed',
    'https://news.mingpao.com/rss/ins/s00005.xml',
    'https://news.mingpao.com/rss/ins/s00024.xml'
    # Add more feeds here
]

def save_new_items_to_pocket(feed_url):
    url = base_url + 'add'
    feed = feedparser.parse(feed_url)
    print(f"Checking {feed_url}...")
    # Process items (oldest first to avoid missing updates)
    for entry in reversed(feed.entries):
        params = {
            'url': entry.link,
            'title': entry.title,
            'consumer_key': CONSUMER_KEY,
            'access_token': ACCESS_TOKEN,
        }
        response = requests.post(url, json=params)
        print(f"URL: {entry.link}")
        print(f"Saved: {entry.title}")
        print(f"API Response: {response.text}")
        time.sleep(1)  # Avoid rate limits

def retrieve(state):
    url = base_url + 'get'
    params = {
        'consumer_key': CONSUMER_KEY,
        'access_token': ACCESS_TOKEN,
        'sort': 'oldest',
        'state': state
    }
    response = requests.post(url, json=params)
    return response.json()

def get_encoded_param(articles, action, days_to_subtract):
    temp = []
    exprange = datetime.now() - timedelta(days=days_to_subtract)
    for article in articles['list'].values():
        artime = datetime.fromtimestamp(int(article['time_added']))
        if article['favorite'] == '0' and artime < exprange:
            obj = {
                'action': action,
                'item_id': article['item_id'],
            }
            temp.append(obj)
    json_temp = json.dumps(temp)
    encoded = urllib.parse.quote(json_temp)
    return encoded, len(temp)

def modify(encodedparam):
    url = base_url + 'send'
    payload = {
        'consumer_key': CONSUMER_KEY,
        'access_token': ACCESS_TOKEN,
        'actions': encodedparam,
    }
    response = requests.post(url, params=payload)
    print(response.text)

def recall(state, action, freq):
    articles = retrieve(state)
    param, length = get_encoded_param(articles, action, freq)
    print(param)
    print(length)
    if length > 0:
        modify(param)
        recall(state, action, freq)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/housekeep", response_class=PlainTextResponse)
async def housekeep():
    recall('unread', 'archive', 1)
    recall('archive', 'delete', 15)
    return "housekeeping is done"

@app.get("/save", response_class=PlainTextResponse)
async def save():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        list(executor.map(save_new_items_to_pocket, RSS_FEEDS))
    return "Saved to pocket"
