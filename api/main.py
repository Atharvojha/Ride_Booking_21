import logging
import os

import psycopg2
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from api.analytics import router as analytics_router
from api.nearby import router as nearby_router
from api.reviews import router as review_router
from api.browse import router as browse_router
from api.common import ApiError
from api.database import mongo, one, postgres
from api.transactions import router as transaction_router

logger = logging.getLogger('ridesync.api')
app = FastAPI(title='RideSync Team 10 API', version='0.2.0',
              description='Assignment demo: browsing, booking, wallet history, revenue, nearby vehicles and reviews.')
app.add_middleware(CORSMiddleware,
                   allow_origins=os.getenv('WEB_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(','),
                   allow_methods=['GET', 'POST', 'PATCH'], allow_headers=['Content-Type'])
app.include_router(nearby_router)
app.include_router(analytics_router)
app.include_router(review_router)
app.include_router(browse_router)
app.include_router(transaction_router)


def error_reply(status, code, message):
    return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message}})


@app.exception_handler(ApiError)
async def api_error(request, exc):
    return error_reply(exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def invalid_input(request, exc):
    fields = sorted({str(item['loc'][-1]) for item in exc.errors() if item.get('loc')})
    message = 'Check these inputs: ' + ', '.join(fields) + '.'
    if 'fareAmount' in fields:
        message = 'Enter a positive fare up to 99,999,999.99 with at most two decimal places.'
        if any(item['loc'][-1] == 'fareAmount' and item['type'] == 'string_type' for item in exc.errors()):
            message = 'Send the fare as text, for example "120.00". It must be positive, up to 99,999,999.99, with at most two decimal places.'
    return error_reply(422, 'INVALID_INPUT', message)


@app.exception_handler(psycopg2.Error)
async def postgres_error(request, exc):
    logger.error('PostgreSQL request failed: %s', type(exc).__name__)
    if isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError)):
        return error_reply(503, 'DATABASE_UNAVAILABLE', 'The data service is unavailable. Try again shortly.')
    return error_reply(500, 'INTERNAL_ERROR', 'The request could not be completed.')


@app.exception_handler(PyMongoError)
async def mongo_error(request, exc):
    logger.error('MongoDB request failed: %s', type(exc).__name__)
    return error_reply(503, 'DATABASE_UNAVAILABLE', 'The data service is unavailable. Try again shortly.')


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logger.exception('Unexpected API failure')
    return error_reply(500, 'INTERNAL_ERROR', 'The request could not be completed.')


@app.get('/api/health')
def health():
    checks = {'postgres': 'ok', 'mongo': 'ok'}
    try:
        with postgres() as conn:
            one(conn, 'SELECT 1')
    except psycopg2.Error:
        checks['postgres'] = 'unavailable'
    try:
        with mongo() as db:
            db.command('ping')
    except PyMongoError:
        checks['mongo'] = 'unavailable'
    return JSONResponse(status_code=200 if all(value == 'ok' for value in checks.values()) else 503,
                        content=checks)
