from typing import Optional
import os
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
batch_size = 6
existurls = []

# Organized RSS feeds by source
RSS_FEEDS = {
    'rthk': [
        'https://rthk9.rthk.hk/rthk/news/rss/c_expressnews_cfinance.xml',
        'https://rthk9.rthk.hk/rthk/news/rss/c_expressnews_clocal.xml'
    ],
    'scmp': [
        'https://www.scmp.com/rss/36/feed',
        'https://www.scmp.com/rss/91/feed'
    ],
    'mingpao': [
        'https://news.mingpao.com/rss/ins/s00005.xml',
        'https://news.mingpao.com/rss/ins/s00024.xml'
    ],
    'all': [
        'https://rthk9.rthk.hk/rthk/news/rss/c_expressnews_cfinance.xml',
        'https://rthk9.rthk.hk/rthk/news/rss/c_expressnews_clocal.xml',
        'https://www.scmp.com/rss/36/feed',
        'https://www.scmp.com/rss/91/feed',
        'https://news.mingpao.com/rss/ins/s00005.xml',
        'https://news.mingpao.com/rss/ins/s00024.xml'
    ]
}

def save_new_items_to_pocket(feed_url):
    """Save new items from an RSS feed to Pocket in batches.
    
    Args:
        feed_url: URL of the RSS feed to process
        batch_size: Number of items to send in each batch (default: 6)
    """
    url = base_url + 'add'
    print(f"Checking {feed_url}...")
    print (f"Existing URLs {existurls}...")
    
    try:
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            print("No entries found in feed.")
            return
            
        # Process items in reverse order (oldest first)
        entries = reversed(feed.entries)
        batch = []
        
        for entry in entries:
            print(entry.link)
            if entry.link not in existurls:
               batch.append({
                "action": "add",
                "url": entry.link,
                "title": entry.title,
               })
            
            if len(batch) >= batch_size:
                _send_batch_to_pocket(batch)
                batch = []
                
        # Send any remaining items in the final partial batch
        if batch:
            _send_batch_to_pocket(batch)
            
    except Exception as e:
        print(f"Error processing feed {feed_url}: {str(e)}")

def _send_batch_to_pocket(batch):
    """Helper function to send a batch of items to Pocket."""
    try:
        json_batch = json.dumps(batch)
        encoded = urllib.parse.quote(json_batch)
        modify(encoded)
    except Exception as e:
        print(f"Error sending batch to Pocket: {str(e)}")

def search_existing(source):
    urlist = []
    url = base_url + 'get'
    params = {
        'consumer_key': CONSUMER_KEY,
        'access_token': ACCESS_TOKEN,
        'sort': 'newest',
        'search': source
    }
    response = requests.post(url, json=params)
    print(response)
    articles = response.json()
    for article in articles['list'].values():
        urlist.append(article['given_url'])
    return urlist

def retrieve(state):
    url = base_url + 'get'
    params = {
        'consumer_key': CONSUMER_KEY,
        'access_token': ACCESS_TOKEN,
        'sort': 'oldest',
        'state': state
    }
    response = requests.post(url, json=params)
    print(response)
    return response.json()

def get_encoded_param(articles, action, delta):
    temp = []
    exprange = datetime.now() - delta
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
    print(response)

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
    return {"message": "kept awake"}

@app.get("/housekeep", response_class=PlainTextResponse)
async def housekeep():
    recall('unread', 'archive', timedelta(hours=12))
    recall('archive', 'delete', timedelta(days=15))
    return "housekeeping is done"

@app.get("/save/{source}", response_class=PlainTextResponse)
async def save_source(source: str):
    """Save specific feed source"""
    print(f"Data source: {source}")
    if source not in RSS_FEEDS:
        return f"Invalid source. Available sources: {', '.join(RSS_FEEDS.keys())}"
    existurls = search_existing(source)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        list(executor.map(save_new_items_to_pocket, RSS_FEEDS[source]))
    return f"Saved {source} feeds to pocket"
