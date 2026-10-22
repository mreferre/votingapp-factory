import os
import hmac

from flask import Flask, render_template, request, session, redirect, url_for, abort
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

# --- Password-protected /votes page ---
# The page fails closed: it is served only when both FLASK_SECRET_KEY (signs the
# session cookie) and VOTES_PAGE_PASSWORD (login) are set, otherwise it returns 404.

app.secret_key = os.getenv('FLASK_SECRET_KEY')
votes_page_password = os.getenv('VOTES_PAGE_PASSWORD')

restaurant_names = ('outback', 'bucadibeppo', 'ihop', 'chipotle')

restaurant_details = {
    'outback': {'display_name': 'Outback Steakhouse', 'emoji': '\U0001f969'},
    'bucadibeppo': {'display_name': 'Buca di Beppo', 'emoji': '\U0001f35d'},
    'ihop': {'display_name': 'IHOP', 'emoji': '\U0001f95e'},
    'chipotle': {'display_name': 'Chipotle', 'emoji': '\U0001f32f'},
}

def votes_page_enabled():
    return bool(app.secret_key) and bool(votes_page_password)

@app.route('/votes/login', methods=['GET', 'POST'])
def votes_login():
    if not votes_page_enabled():
        abort(404)
    error = None
    if request.method == 'POST':
        submitted_password = request.form.get('password', '')
        if hmac.compare_digest(submitted_password.encode('utf-8'), votes_page_password.encode('utf-8')):
            session['votes_authenticated'] = True
            return redirect(url_for('votes'))
        error = 'Incorrect password. Please try again.'
    status = 401 if error else 200
    return render_template('votes_login.html', error=error), status

@app.route('/votes')
def votes():
    if not votes_page_enabled():
        abort(404)
    if not session.get('votes_authenticated'):
        return redirect(url_for('votes_login'))
    restaurant_votes = []
    for name in restaurant_names:
        try:
            count = int(readvote(name))
        except KeyError:
            # a restaurant without a DynamoDB item shows as 0 votes
            count = 0
        details = restaurant_details[name]
        restaurant_votes.append({'name': name, 'display_name': details['display_name'], 'emoji': details['emoji'], 'votes': count})
    return render_template('votes.html', restaurants=restaurant_votes)

@app.route('/votes/logout')
def votes_logout():
    if not votes_page_enabled():
        abort(404)
    session.clear()
    return redirect(url_for('votes_login'))

if __name__ == '__main__':
   app.run(host=os.getenv('IP', '0.0.0.0'), port=int(os.getenv('PORT', 8080)))
   app.debug =True
