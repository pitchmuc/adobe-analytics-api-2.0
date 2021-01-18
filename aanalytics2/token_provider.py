import os
import time
from typing import Dict, Union

import jwt
import requests

from aanalytics2 import configs


def get_token_and_expiry_for_config(config: dict, verbose: bool = False, save: bool = False, *args, **kwargs) -> \
        Dict[str, str]:
    """
    Retrieve the token by using the information provided by the user during the import importConfigFile function.
    ArgumentS :
        verbose : OPTIONAL : Default False. If set to True, print information.
        save : OPTIONAL : Default False. If set to True, save the toke in the .
    """
    private_key = configs.get_private_key_from_config(config)
    header_jwt = {
        'cache-control': 'no-cache',
        'content-type': 'application/x-www-form-urlencoded'
    }
    now_plus_24h = int(time.time()) + 24 * 60 * 60
    jwt_payload = {
        'exp': now_plus_24h,
        'iss': config['org_id'],
        'sub': config['tech_id'],
        'https://ims-na1.adobelogin.com/s/ent_analytics_bulk_ingest_sdk': True,
        'aud': f'https://ims-na1.adobelogin.com/c/{config["client_id"]}'
    }
    encoded_jwt = _get_jwt(payload=jwt_payload, private_key=private_key)

    payload = {
        'client_id': config['client_id'],
        'client_secret': config['secret'],
        'jwt_token': encoded_jwt
    }
    response = requests.post(config['tokenEndpoint'], headers=header_jwt, data=payload)
    json_response = response.json()
    try:
        token = json_response['access_token']
    except KeyError:
        print('Issue retrieving token')
        print(json_response)
    expiry = json_response['expires_in']
    if save:
        with open('token.txt', 'w') as f:
            f.write(token)
        print(f'token has been saved here: {os.getcwd()}{os.sep}token.txt')
    if verbose:
        print('token valid till : ' + time.ctime(time.time() + expiry / 1000))
    return {'token': token, 'expiry': expiry}


def _get_jwt(payload: dict, private_key: str) -> str:
    token: Union[str, bytes] = jwt.encode(payload, private_key, algorithm='RS256')
    if isinstance(token, bytes):
        return token.decode('utf-8')
    return token
