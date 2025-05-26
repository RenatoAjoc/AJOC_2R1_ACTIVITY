from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated
from passlib.hash import phpass
from datetime import datetime, timedelta, timezone
from errors import http_auth_err

from constants import JWT_SETTINGS
from connector import MYSQLQuery, vdbpool


pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def rest_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = http_auth_err('Could not validate credentials')
    try:
        payload = jwt.decode(token, JWT_SETTINGS['secret_key'], algorithms=[JWT_SETTINGS['algorithm']])
        identifier = payload.get('sub')
        if identifier == None: raise credentials_exception
    except JWTError: raise credentials_exception
    
    user = get_user(identifier)
    if user == None: raise credentials_exception
    return user


def get_user(identifier: str) -> dict | None:
    db_obj = MYSQLQuery(vdbpool)
    user_data = db_obj.read('SELECT user_id, username, email, role, region, name FROM vanguard_users WHERE username = %s OR email = %s LIMIT 1', (identifier, identifier))
    if user_data: return {
        'id': user_data[0][0],
        'username': user_data[0][1],
        'email': user_data[0][2],
        'role': user_data[0][3],
        'region': user_data[0][4],
        'name': user_data[0][5]
    }
    return None


def verify_user(identifier: str, password: str) -> bool:
    db_obj = MYSQLQuery(vdbpool)
    _hashed = db_obj.read('SELECT password FROM vanguard_users WHERE username = %s OR email = %s LIMIT 1', (identifier, identifier,))
    if _hashed: return pwd_context.verify(password, _hashed[0][0])
    return False


def authenticate_user(identifier: str, password: str) -> dict | bool:
    verify = verify_user(identifier, password)
    if not verify: return False
    user = get_user(identifier)
    if not user: return False
    return user


def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({ "exp": expire })
    encoded_jwt = jwt.encode(to_encode, JWT_SETTINGS['secret_key'], algorithm=JWT_SETTINGS['algorithm'])
    return encoded_jwt


def ws_user(token: str):
    try:
        payload = jwt.decode(token, JWT_SETTINGS['secret_key'], algorithms=[JWT_SETTINGS['algorithm']])
        identifier = payload.get('sub')
        if identifier == None or payload.get('id') == None: return None

    except JWTError: return None
    user = get_user(identifier)
    if user == None: return None
    return user




