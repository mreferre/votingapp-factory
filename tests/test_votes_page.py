"""Tests for the password protected /votes page. DynamoDB is replaced by an in-memory fake."""
import importlib
import json
import os
import re

import pytest

os.environ.setdefault('AWS_DEFAULT_REGION', 'us-west-2')
os.environ.setdefault('AWS_ACCESS_KEY_ID', 'test')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'test')

PASSWORD = 'correct horse'
IDS = ['outback', 'bucadibeppo', 'ihop', 'chipotle']


class FakeTable:
    def __init__(self):
        self.items = {name: n * 10 for n, name in enumerate(IDS)}

    def get_item(self, Key):
        return {'Item': {'name': Key['name'], 'restaurantcount': self.items[Key['name']]}}

    def update_item(self, Key, ExpressionAttributeValues, **_):
        self.items[Key['name']] = ExpressionAttributeValues[':value']


def load_app(monkeypatch, password=PASSWORD, secret='test-secret'):
    for var, value in (('VOTES_PAGE_PASSWORD', password), ('FLASK_SECRET_KEY', secret)):
        if value is None:
            monkeypatch.delenv(var, raising=False)
        else:
            monkeypatch.setenv(var, value)
    import app as app_module
    app_module = importlib.reload(app_module)
    app_module.ddbtable = FakeTable()
    return app_module


@pytest.fixture
def appmod(monkeypatch):
    return load_app(monkeypatch)


@pytest.fixture
def client(appmod):
    return appmod.app.test_client()


def token(html):
    return re.search(r'name="csrf_token" value="([0-9a-f]+)"', html).group(1)


def login(client, password=PASSWORD):
    page = client.get('/votes/login')
    return client.post('/votes/login', data={'password': password, 'csrf_token': token(page.get_data(as_text=True))})


def test_unauthenticated_redirects_to_login(client):
    response = client.get('/votes')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/votes/login')


def test_wrong_password_rejected(client):
    response = login(client, 'nope')
    assert response.status_code == 401
    assert 'Incorrect password' in response.get_data(as_text=True)
    assert client.get('/votes').status_code == 302


def test_login_without_csrf_rejected(client):
    client.get('/votes/login')
    assert client.post('/votes/login', data={'password': PASSWORD}).status_code == 401
    assert client.get('/votes').status_code == 302


def test_correct_password_shows_grid_with_counts(client):
    response = login(client)
    assert response.status_code == 302
    page = client.get('/votes')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    for name, label in (('outback', 'Outback'), ('bucadibeppo', 'Buca di Beppo'), ('ihop', 'IHOP'), ('chipotle', 'Chipotle')):
        assert 'data-id="%s"' % name in html and label in html
    counts = re.findall(r'data-count>(\d+)<', html)
    assert counts == ['0', '10', '20', '30']


def test_vote_increments_and_persists(client, appmod):
    login(client)
    csrf = token_from_vote_page(client)
    response = client.post('/votes/vote/ihop', headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200
    assert response.get_json() == {'id': 'ihop', 'votes': 21}
    assert appmod.ddbtable.items['ihop'] == 21
    data = client.get('/votes/data').get_json()
    assert [r['votes'] for r in data['restaurants']] == [0, 10, 21, 30]


def token_from_vote_page(client):
    return re.search(r'data-csrf="([0-9a-f]+)"', client.get('/votes').get_data(as_text=True)).group(1)


def test_vote_requires_login(client, appmod):
    assert client.post('/votes/vote/ihop').status_code == 401
    assert client.get('/votes/data').status_code == 401
    assert appmod.ddbtable.items['ihop'] == 20


def test_vote_requires_csrf_and_known_restaurant(client, appmod):
    login(client)
    csrf = token_from_vote_page(client)
    assert client.post('/votes/vote/ihop').status_code == 403
    assert client.post('/votes/vote/ihop', headers={'X-CSRF-Token': 'bad'}).status_code == 403
    assert client.post('/votes/vote/nowhere', headers={'X-CSRF-Token': csrf}).status_code == 404
    assert appmod.ddbtable.items['ihop'] == 20


def test_logout(client):
    login(client)
    csrf = token_from_vote_page(client)
    assert client.post('/votes/logout').status_code == 302
    assert client.get('/votes').status_code == 302
    assert client.post('/votes/vote/ihop', headers={'X-CSRF-Token': csrf}).status_code == 401


@pytest.mark.parametrize('password,secret', [(None, 'secret'), (PASSWORD, None), (None, None), ('', 'secret')])
def test_fails_closed_when_not_configured(monkeypatch, password, secret):
    client = load_app(monkeypatch, password, secret).app.test_client()
    for path in ('/votes', '/votes/login', '/votes/data'):
        assert client.get(path).status_code == 404
    assert client.post('/votes/login', data={'password': ''}).status_code == 404
    assert client.post('/votes/vote/ihop').status_code == 404


def test_existing_routes_unchanged(client, appmod):
    assert 'Welcome to the Voting App' in client.get('/').get_data(as_text=True)
    assert client.get('/api/outback').get_data(as_text=True) == '1'
    assert json.loads(client.get('/api/getvotes').get_data(as_text=True)) == [
        {'name': 'outback', 'value': 1}, {'name': 'bucadibeppo', 'value': 10},
        {'name': 'ihop', 'value': 20}, {'name': 'chipotle', 'value': 30}]


def test_password_not_hardcoded():
    source = open(os.path.join(os.path.dirname(__file__), '..', 'app.py')).read()
    assert PASSWORD not in source
