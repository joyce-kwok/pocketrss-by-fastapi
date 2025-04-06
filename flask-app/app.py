from flask import Flask

app = Flask(__name__)

@app.route('/adduser')
def flask_endpoint():
    return "Hello from Flask!"

