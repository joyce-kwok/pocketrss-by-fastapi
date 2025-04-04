from typing import Optional
import os
import concurrent.futures
import feedparser
import time
import requests
import json
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi import FastAPI

app = FastAPI()
CONSUMER_KEY = os.getenv('CONSUMER_KEY')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
base_url = 'https://getpocket.com/v3/'
batch_size = 8
existurls = []
last_update: datetime = datetime.min.replace(tzinfo=timezone.utc)

# Organized RSS feeds by source
RSS_FEEDS = {
    'bbc': [
        'https://feeds.bbci.co.uk/news/world/rss.xml',
        'https://feeds.bbci.co.uk/news/technology/rss.xml',
        'https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml'
    ],
    'cnn':[
        'http://rss.cnn.com/rss/money_pf.rss',
        'http://rss.cnn.com/rss/money_technology.rss',
        'http://rss.cnn.com/rss/money_news_economy.rss',
        'http://rss.cnn.com/rss/money_news_international.rss',
        'http://rss.cnn.com/rss/money_markets.rss'
    ]
    'rthk': [
        'https://rthk9.rthk.hk/rthk/news/rss/c_expressnews_cfinance.xml',
        'https://rthk9.rthk.hk/rthk/news/rss/c_expressnews_clocal.xml'
    ],
    'scmp': [
        'https://www.scmp.com/rss/2/feed',
        'https://www.scmp.com/rss/318255/feed'
    ],
    'mingpao': [
        'https://news.mingpao.com/rss/ins/s00005.xml',
        'https://news.mingpao.com/rss/ins/s00024.xml'
    ],
    'telegraph': [
        'https://www.telegraph.co.uk/rss.xml'
    ],
    'nytimes': [
        'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
        'https://rss.nytimes.com/services/xml/rss/nyt/PersonalTech.xml',
        'https://rss.nytimes.com/services/xml/rss/nyt/tmagazine.xml'
    ],
    'washingtonpost': [
        'https://feeds.washingtonpost.com/rss/lifestyle',
        'https://feeds.washingtonpost.com/rss/business/technology'
    ],
    'hket':[
        'https://www.hket.com/rss/hongkong'
    ],
    'newtalk':[
        'https://newtalk.tw/rss/category/8',
    ],
    'ltn':[
        'https://news.ltn.com.tw/rss/world.xml'
    ],
    'dowjones':[
        'https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness',
        'https://feeds.content.dowjones.io/public/rss/RSSMarketsMain',
        'https://feeds.content.dowjones.io/public/rss/RSSWSJD'
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
    # print (f"Existing URLs {existurls}...")
    
    try:
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            print("No entries found in feed.")
            return
            
        # Process items in reverse order (oldest first)
        entries = reversed(feed.entries)
        batch = []
        
        for entry in entries:
            published_datetime = parsedate_to_datetime(entry.published)
            unix_timestamp = int(published_datetime.timestamp())
            # print(f"Checking if {entry.link} is a new link... ")
            if entry.link not in existurls and published_datetime > last_update:
               print(f"{entry.link} is a new link and will be pushed")
               print(f"Original Published Time: {entry.published}, Unix Timestamp (in integer): {unix_timestamp}")
               batch.append({
                "action": "add",
                "url": entry.link,
                "title": entry.title,
                "time": unix_timestamp
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
    latest = datetime.min.replace(tzinfo=timezone.utc)
    url = base_url + 'get'
    params = {
        'consumer_key': CONSUMER_KEY,
        'access_token': ACCESS_TOKEN,
        'sort': 'newest',
        'search': source
    }
    response = requests.post(url, json=params)
    print(f"Calling retrieve API to search saved posts, response code is {response.status_code}")
    if response.status_code == 200:
       articles = response.json()
       article_list = articles['list']
       if len(article_list) > 0:
          last_item_key = next(reversed(article_list))  # Returns "4192836625"
          last_item = article_list[last_item_key] # Returns the full last item dict
          latest = datetime.fromtimestamp(int(last_item['time_added']), tz=timezone.utc)
          print(f"Last updated: {latest}")
          for article in article_list.values():
              urlist.append(article['given_url'])
       else:
          print("No existing articles for this news source") 
          print(f"Last updated: {latest}")
    else:
        urlist.append('error')
    return urlist, latest, response.status_code

def retrieve(state):
    url = base_url + 'get'
    params = {
        'consumer_key': CONSUMER_KEY,
        'access_token': ACCESS_TOKEN,
        'state': state,
        'favorite': 0,
        'sort': 'oldest',
    }
    response = requests.post(url, json=params)
    print(f"Calling retrieve API for {state} action, response code is {response.status_code}")
    return response.json()

def get_encoded_param(articles, action, delta):
    temp = []
    exprange = datetime.now() - delta
    for article in articles['list'].values():
        artime = datetime.fromtimestamp(int(article['time_added']))
        if artime < exprange:
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
    print(f"Calling modify API to update items, response code is {response.status_code}")

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

@app.get("/housekeep/{action}", response_class=PlainTextResponse)
async def housekeep(action: str):
    if action == 'archive': 
       recall('unread', 'archive', timedelta(hours=12))
    if action == 'delete':
       recall('archive', 'delete', timedelta(days=15))
    return "housekeeping is done"

@app.get("/save/{source}", response_class=PlainTextResponse)
async def save_source(source: str):
    global existurls, last_update
    """Save specific feed source"""
    print(f"Data source: {source}")
    if source not in RSS_FEEDS:
        return f"Invalid source. Available sources: {', '.join(RSS_FEEDS.keys())}"
    existurls, last_update, code = search_existing(source)
    if code == 200:
        with concurrent.futures.ThreadPoolExecutor() as executor:
          list(executor.map(save_new_items_to_pocket, RSS_FEEDS[source]))
        return f"Saved {source} feeds to pocket"
    else:
        return f"Cannot retrieve saved {source} feeds at the moment. Will not update news in this run."
