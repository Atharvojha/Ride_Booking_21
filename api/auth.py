"""Sessions and roles for the RideSync API: admin and rider.

* admin: signs in with ADMIN_USERNAME / ADMIN_PASSWORD from the environment.
  Admins can read and change everything. With no ADMIN_PASSWORD, admin sign-in is off.
* rider: the seeded riders have no passwords, so a rider "signs in" by choosing
  their name (demo sign-in, on by default; set RIDER_DEMO_LOGIN=0 to switch it off).
  A rider can only read or change their own wallet, trips and bookings.

A session is a signed, HttpOnly, SameSite=Strict cookie. Nothing is stored in a
database and no extra packages are needed.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict, deque
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from api.common import ApiError, Page, PageSize, Search, listing
from api.database import one, postgres

COOKIE = 'ridesync_session'
SESSION_SECONDS = 8 * 60 * 60
MAX_FAILURES, FAILURE_WINDOW = 5, 60
# Used only when ADMIN_SESSION_SECRET is not set: sessions then end on restart.
_process_secret = secrets.token_bytes(32)
_failures = defaultdict(deque)

router = APIRouter(prefix='/api/session')


class AdminLogin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


class RiderLogin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    riderId: UUID


def _secret():
    configured = os.getenv('ADMIN_SESSION_SECRET')
    return configured.encode() if configured else _process_secret


def _sign(payload):
    return hmac.new(_secret(), payload, hashlib.sha256).hexdigest()


def _same(a, b):
    # Hash first so inputs of different lengths compare in the same time.
    return hmac.compare_digest(hashlib.sha256(a.encode()).digest(), hashlib.sha256(b.encode()).digest())


def make_token(role, subject, name, now=None):
    start = time.time() if now is None else now
    body = json.dumps({'r': role, 's': subject, 'n': name, 'exp': int(start + SESSION_SECONDS)}).encode()
    payload = base64.urlsafe_b64encode(body).decode()
    return payload + '.' + _sign(payload.encode())


def current_session(request: Request):
    """The signed-in {role, id, name}, or None."""
    payload, _, signature = request.cookies.get(COOKIE, '').partition('.')
    if not payload or not hmac.compare_digest(signature, _sign(payload.encode())):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        if data['exp'] < time.time() or data['r'] not in ('admin', 'rider'):
            return None
        if data['r'] == 'admin' and (not os.getenv('ADMIN_PASSWORD')
                                     or data['s'] != os.getenv('ADMIN_USERNAME', 'admin')):
            return None  # a removed password or renamed admin ends old admin sessions
        return {'role': data['r'], 'id': data['s'], 'name': data['n']}
    except (ValueError, KeyError, TypeError):
        return None


def require_session(request: Request):
    session = current_session(request)
    if session is None:
        raise ApiError(401, 'SESSION_REQUIRED', 'Sign in as a rider or an admin to continue.')
    return session


def require_admin(request: Request):
    session = require_session(request)
    if session['role'] != 'admin':
        raise ApiError(403, 'ADMIN_REQUIRED', 'Only admins can do this.')
    return session


def check_rider(session, rider_id):
    """Admins may use any rider; a rider only themselves."""
    if session['role'] != 'admin' and session['id'] != str(rider_id):
        raise ApiError(403, 'FORBIDDEN', 'You can only use your own rider account.')


def scope_rider(session, rider_id):
    """The rider a list should be limited to: always the rider themselves, or any (None = all) for admins."""
    if session['role'] == 'admin':
        return rider_id
    check_rider(session, rider_id if rider_id is not None else session['id'])
    return UUID(session['id'])


def _set_cookie(response, token):
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite='strict',
                        secure=os.getenv('ADMIN_COOKIE_SECURE') == '1', path='/api')


def _describe(session):
    return {'role': session['role'], 'id': session['id'], 'name': session['name']} if session else \
        {'role': None, 'id': None, 'name': None}


@router.get('')
def who(request: Request):
    return _describe(current_session(request))


@router.post('/admin')
def admin_login(body: AdminLogin, request: Request, response: Response):
    expected = os.getenv('ADMIN_PASSWORD')
    if not expected:
        raise ApiError(503, 'ADMIN_DISABLED', 'Admin sign-in is not set up. Set ADMIN_PASSWORD in .env and restart the API.')
    host = request.client.host if request.client else 'unknown'
    attempts, now = _failures[host], time.time()
    while attempts and now - attempts[0] > FAILURE_WINDOW:
        attempts.popleft()
    if len(attempts) >= MAX_FAILURES:
        raise ApiError(429, 'TOO_MANY_ATTEMPTS', 'Too many failed sign-ins. Wait a minute and try again.')
    username = os.getenv('ADMIN_USERNAME', 'admin')
    # Check both fields every time so a wrong username takes as long as a wrong password.
    if not (_same(body.username, username) & _same(body.password, expected)):
        attempts.append(now)
        raise ApiError(401, 'INVALID_CREDENTIALS', 'Incorrect username or password.')
    attempts.clear()
    _set_cookie(response, make_token('admin', username, username))
    return {'role': 'admin', 'id': username, 'name': username}


def _demo_enabled():
    return os.getenv('RIDER_DEMO_LOGIN', '1') != '0'


@router.post('/rider')
def rider_login(body: RiderLogin, response: Response):
    if not _demo_enabled():
        raise ApiError(403, 'RIDER_LOGIN_DISABLED', 'Rider sign-in is switched off.')
    with postgres() as conn:
        row = one(conn, 'SELECT id, name FROM riders WHERE id=%s', [body.riderId])
    if row is None:
        raise ApiError(404, 'NOT_FOUND', 'This rider could not be found.')
    _set_cookie(response, make_token('rider', str(row['id']), row['name']))
    return {'role': 'rider', 'id': str(row['id']), 'name': row['name']}


@router.get('/riders')
def demo_riders(search: Search = '', page: Page = 1, pageSize: PageSize = 10):
    """Names only, for the demo rider sign-in list. Balances are not included."""
    if not _demo_enabled():
        raise ApiError(403, 'RIDER_LOGIN_DISABLED', 'Rider sign-in is switched off.')
    with postgres() as conn:
        return listing(conn, 'riders', 'id, name', ['(name ILIKE %s OR id::text ILIKE %s)'],
                       ['%' + search + '%'] * 2, 'name, id', page, pageSize,
                       lambda row: {'id': str(row['id']), 'name': row['name']})


@router.post('/logout')
def logout(response: Response):
    response.delete_cookie(COOKIE, path='/api')
    return _describe(None)
