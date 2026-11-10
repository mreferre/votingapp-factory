"""Tests for the voting API, run against an in-memory DynamoDB (moto).

Run with: pip install pytest "moto[dynamodb]" && pytest test_app.py
"""
import importlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import boto3
import pytest
from moto import mock_aws

TABLE = "votingapp-restaurants"
RESTAURANTS = ("outback", "bucadibeppo", "ihop", "chipotle")


@pytest.fixture
def client():
    os.environ.update(DDB_AWS_REGION="us-east-1", DDB_TABLE_NAME=TABLE,
                      AWS_ACCESS_KEY_ID="test", AWS_SECRET_ACCESS_KEY="test")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "name", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "name", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        for name in RESTAURANTS:
            table.put_item(Item={"name": name, "restaurantcount": 0})
        sys.modules.pop("app", None)
        app = importlib.import_module("app")
        yield app.app.test_client()


def test_vote_increments_and_returns_new_total(client):
    assert client.get("/api/ihop").data == b"1"
    assert client.get("/api/ihop").data == b"2"


def test_unknown_restaurant_is_404(client):
    assert client.get("/api/mcdonalds").status_code == 404


def test_getvotes_shape_and_order(client):
    client.get("/api/outback")
    client.get("/api/chipotle")
    client.get("/api/chipotle")
    resp = client.get("/api/getvotes")
    assert resp.status_code == 200
    assert resp.get_json() == [
        {"name": "outback", "value": 1},
        {"name": "bucadibeppo", "value": 0},
        {"name": "ihop", "value": 0},
        {"name": "chipotle", "value": 2},
    ]


def test_concurrent_votes_are_not_lost(client):
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: client.get("/api/outback"), range(50)))
    votes = {v["name"]: v["value"] for v in client.get("/api/getvotes").get_json()}
    assert votes["outback"] == 50
