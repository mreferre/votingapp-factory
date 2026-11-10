import os

from flask import Flask, abort, jsonify
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

# Restaurants that can be voted for, in the order /api/getvotes returns them.
RESTAURANTS = ("outback", "bucadibeppo", "ihop", "chipotle")

def addvote(restaurant):
    """Atomically add one vote and return the new total.

    A single ADD update avoids the old read-then-write race, where two
    concurrent votes could read the same count and one vote was lost.
    """
    response = ddbtable.update_item(
        Key={'name': restaurant},
        UpdateExpression='ADD restaurantcount :one',
        ExpressionAttributeValues={':one': 1},
        ReturnValues='UPDATED_NEW'
    )
    return int(response["Attributes"]["restaurantcount"])

def readallvotes():
    """Read every restaurant's count in one BatchGetItem call."""
    response = ddb.batch_get_item(
        RequestItems={
            ddb_table_name: {'Keys': [{'name': name} for name in RESTAURANTS]}
        }
    )
    counts = {
        item['name']: int(item['restaurantcount'])
        for item in response['Responses'].get(ddb_table_name, [])
    }
    # BatchGetItem returns items in any order; keep the original response order.
    return [{"name": name, "value": counts[name]} for name in RESTAURANTS]

@app.route('/')
def home():
    return "<h1>Welcome to the Voting App</h1><p><b>To vote, you can call the following APIs:</b></p><p>/api/outback</p><p>/api/bucadibeppo</p><p>/api/ihop</p><p>/api/chipotle</p><b>To query the votes, you can call the following APIs:</b><p>/api/getvotes</p><p>/api/getheavyvotes (this generates artificial CPU/memory load)</p>"

@app.route("/api/<restaurant>")
def vote(restaurant):
    if restaurant not in RESTAURANTS:
        abort(404)
    return str(addvote(restaurant))

@app.route("/api/getvotes")
def getvotes():
    return jsonify(readallvotes())

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

if __name__ == '__main__':
   app.run(host=os.getenv('IP', '0.0.0.0'), port=int(os.getenv('PORT', 8080)))
