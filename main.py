import os, time, secrets
import concurrent.futures
import feedparser
import requests, json
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Annotated
<<<<<<< HEAD:fastapi-app/main.py
=======
from pydantic import BaseModel, Field
from flask import Flask
>>>>>>> parent of 00d3a36 (Separate frontend and backend):main.py
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import PlainTextResponse

fastAPIapp = FastAPI()
flaskapp = Flask(__name__)
security = HTTPBasic()

CONSUMER_KEY = os.getenv('CONSUMER_KEY')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
username = os.getenv('username')
password = os.getenv('password')
base_url = 'https://getpocket.com/v3/'
batch_size = 8
existurls = []
last_update: datetime = datetime.min.replace(tzinfo=timezone.utc)

class HousekeepRequest(BaseModel):
    action: str
    hours: int = Field(default=None)
    days: int = Field(default=None)
    weeks: int = Field(default=None)
    minutes: int = Field(default=None)

def run_flask():
    flaskapp.run(host="0.0.0.0", port=5000)  # Use a different port for Flask

@flaskapp.route('/adduser')
def flask_endpoint():
    return "Hello from Flask!"

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

def authenticate(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
):
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = username.encode("utf8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = password.encode("utf8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return is_correct_username and is_correct_password


@fastAPIapp.get("/")
async def root():
    return {"message": "kept awake"}

@fastAPIapp.post("/housekeep", response_class=PlainTextResponse)
async def housekeep(request: HousekeepRequest, verification: bool = Depends(authenticate)):
    if verification:
        time_delta = timedelta(
            days=request.days if request.days else 0,
            hours=request.hours if request.hours else 0,
            minutes=request.minutes if request.minutes else 0,
            weeks=request.weeks if request.weeks else 0
        )

        if request.action == 'archive':
            recall('unread', 'archive', time_delta)
        elif request.action == 'delete':
            recall('archive', 'delete', time_delta)
        else:
            return "Invalid request parameters"

        return "housekeeping is done"
    else:
        return "Unauthorized"

@fastAPIapp.get("/save/{source}", response_class=PlainTextResponse)
async def save_source(source: str, verification: bool = Depends(authenticate)):
    global existurls, last_update
    """Save specific feed source"""
    print(f"Data source: {source}")
    if verification: 
       # Load RSS_FEEDS from JSON config
       with open('config.json') as config_file:
            config = json.load(config_file)
            RSS_FEEDS = config['RSS_FEEDS']
       if source not in RSS_FEEDS:
          return f"Invalid source. Available sources: {', '.join(RSS_FEEDS.keys())}"
       existurls, last_update, code = search_existing(source)
       if code == 200:
          with concurrent.futures.ThreadPoolExecutor() as executor:
               list(executor.map(save_new_items_to_pocket, RSS_FEEDS[source]))
          return f"Saved {source} feeds to pocket"
       else:
          return f"Cannot retrieve saved {source} feeds at the moment. Will not update news in this run."
