import hmac
import os
import secrets

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS, cross_origin
from random import randrange
import simplejson as json
import boto3
from multiprocessing import Pool
from multiprocessing import cpu_count

app = Flask(__name__)

cors = CORS(app, resources={r"/api/*": {"Access-Control-Allow-Origin": "*"}})

cpustressfactor = os.getenv('CPUSTRESSFACTOR', 1)
memstressfactor = os.getenv('MEMSTRESSFACTOR', 1)
ddb_aws_region = os.getenv('DDB_AWS_REGION')
ddb_table_name = os.getenv('DDB_TABLE_NAME', "votingapp-restaurants")

# Settings for the password protected /votes page. Both must be set, otherwise the page is disabled (404).
votes_page_password = os.getenv('VOTES_PAGE_PASSWORD')
app.secret_key = os.getenv('FLASK_SECRET_KEY')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

RESTAURANTS = [
    {"id": "outback", "label": "Outback"},
    {"id": "bucadibeppo", "label": "Buca di Beppo"},
    {"id": "ihop", "label": "IHOP"},
    {"id": "chipotle", "label": "Chipotle"},
]

ddb = boto3.resource('dynamodb', region_name=ddb_aws_region)
ddbtable = ddb.Table(ddb_table_name)

print("The cpustressfactor variable is set to: " + str(cpustressfactor))
print("The memstressfactor variable is set to: " + str(memstressfactor))
memeater=[]
memeater=[0 for i in range(10000)] 

## https://gist.github.com/tott/3895832
def f(x):
    for x in range(1000000 * int(cpustressfactor)):
        x*x

def readvote(restaurant):
    response = ddbtable.get_item(Key={'name': restaurant})
    # this is required to convert decimal to integer 
    normilized_response = json.dumps(response)
    json_response = json.loads(normilized_response)
    votes = json_response["Item"]["restaurantcount"]
    return str(votes)

def updatevote(restaurant, votes):
    ddbtable.update_item(
        Key={
            'name': restaurant
        },
        UpdateExpression='SET restaurantcount = :value',
        ExpressionAttributeValues={
            ':value': votes
        },
        ReturnValues='UPDATED_NEW'
    )
    return str(votes)

@app.route('/')
def home():
    return "<h1>Welcome to the Voting App</h1><p><b>To vote, you can call the following APIs:</b></p><p>/api/outback</p><p>/api/bucadibeppo</p><p>/api/ihop</p><p>/api/chipotle</p><b>To query the votes, you can call the following APIs:</b><p>/api/getvotes</p><p>/api/getheavyvotes (this generates artificial CPU/memory load)</p>"

@app.route("/api/outback")
def outback():
    string_votes = readvote("outback")
    votes = int(string_votes)
    votes += 1
    string_new_votes = updatevote("outback", votes)
    return string_new_votes 

@app.route("/api/bucadibeppo")
def bucadibeppo():
    string_votes = readvote("bucadibeppo")
    votes = int(string_votes)
    votes += 1
    string_new_votes = updatevote("bucadibeppo", votes)
    return string_new_votes 

@app.route("/api/ihop")
def ihop():
    string_votes = readvote("ihop")
    votes = int(string_votes)
    votes += 1
    string_new_votes = updatevote("ihop", votes)
    return string_new_votes 

@app.route("/api/chipotle")
def chipotle():
    string_votes = readvote("chipotle")
    votes = int(string_votes)
    votes += 1
    string_new_votes = updatevote("chipotle", votes)
    return string_new_votes 

@app.route("/api/getvotes")
def getvotes():
    string_outback = readvote("outback")
    string_ihop = readvote("ihop")
    string_bucadibeppo = readvote("bucadibeppo")
    string_chipotle = readvote("chipotle")
    string_votes = '[{"name": "outback", "value": ' + string_outback + '},' + '{"name": "bucadibeppo", "value": ' + string_bucadibeppo + '},' + '{"name": "ihop", "value": '  + string_ihop + '}, ' + '{"name": "chipotle", "value": '  + string_chipotle + '}]'
    return string_votes

@app.route("/api/getheavyvotes")
def getheavyvotes():
    string_outback = readvote("outback")
    string_ihop = readvote("ihop")
    string_bucadibeppo = readvote("bucadibeppo")
    string_chipotle = readvote("chipotle")
    string_votes = '[{"name": "outback", "value": ' + string_outback + '},' + '{"name": "bucadibeppo", "value": ' + string_bucadibeppo + '},' + '{"name": "ihop", "value": '  + string_ihop + '}, ' + '{"name": "chipotle", "value": '  + string_chipotle + '}]'
    print("You invoked the getheavyvotes API. I am eating 100MB * " + str(memstressfactor) + " at every votes request")
    memeater[randrange(10000)] = bytearray(1024 * 1024 * 100 * memstressfactor, encoding='utf8') # eats 100MB * memstressfactor
    print("You invoked the getheavyvotes API. I am eating some cpu * " + str(cpustressfactor) + " at every votes request")
    processes = cpu_count()
    pool = Pool(processes)
    pool.map(f, range(processes))
    return string_votes

## Password protected /votes page (UI). The /api/* routes above are unchanged and remain public.

def votes_page_enabled():
    return bool(votes_page_password) and bool(app.secret_key)

def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_hex(16)
    return session['csrf']

def csrf_valid(candidate):
    return bool(candidate) and hmac.compare_digest(str(candidate), session.get('csrf', ''))

@app.before_request
def votes_fail_closed():
    # Fail closed: without a configured password and secret key the whole /votes area does not exist.
    if request.path.startswith('/votes') and not votes_page_enabled():
        abort(404)

def read_all_votes():
    return [{"id": r["id"], "label": r["label"], "votes": int(readvote(r["id"]))} for r in RESTAURANTS]

@app.route('/votes')
def votes_page():
    if not session.get('authenticated'):
        return redirect(url_for('votes_login'))
    return render_template('votes.html', restaurants=read_all_votes(), csrf_token=csrf_token())

@app.route('/votes/login', methods=['GET', 'POST'])
def votes_login():
    error = None
    if request.method == 'POST':
        password_ok = hmac.compare_digest(request.form.get('password', '').encode('utf-8'), votes_page_password.encode('utf-8'))
        if not csrf_valid(request.form.get('csrf_token')):
            error = "Your session expired. Please try again."
        elif not password_ok:
            error = "Incorrect password."
        else:
            session.clear()
            session['authenticated'] = True
            return redirect(url_for('votes_page'))
    return render_template('votes_login.html', error=error, csrf_token=csrf_token()), (401 if error else 200)

@app.route('/votes/logout', methods=['POST'])
def votes_logout():
    session.clear()
    return redirect(url_for('votes_login'))

@app.route('/votes/data')
def votes_data():
    if not session.get('authenticated'):
        return jsonify(error="unauthorized"), 401
    return jsonify(restaurants=read_all_votes())

@app.route('/votes/vote/<restaurant>', methods=['POST'])
def votes_vote(restaurant):
    if not session.get('authenticated'):
        return jsonify(error="unauthorized"), 401
    if not csrf_valid(request.headers.get('X-CSRF-Token')):
        return jsonify(error="invalid csrf token"), 403
    if restaurant not in [r["id"] for r in RESTAURANTS]:
        return jsonify(error="unknown restaurant"), 404
    new_votes = int(updatevote(restaurant, int(readvote(restaurant)) + 1))
    return jsonify(id=restaurant, votes=new_votes)

if __name__ == '__main__':
   app.run(host=os.getenv('IP', '0.0.0.0'), port=int(os.getenv('PORT', 8080)))
   app.debug =True
