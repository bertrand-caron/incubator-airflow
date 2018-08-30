# -*- coding: utf-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from functools import wraps
from future.standard_library import install_aliases

from airflow.utils.log.logging_mixin import LoggingMixin

install_aliases()

import requests
import json

from airflow import configuration as conf

from flask import Response
from flask import _request_ctx_stack as stack
from flask import make_response
from flask import request
from functools import wraps

ACCESS_API_URL = None
client_auth = None


log = LoggingMixin().log


def get_config_param(param):
    return str(conf.get('auth0', param))


def init_app(app):
    global ACCESS_API_URL
    ACCESS_API_URL = str(conf.get('roames', 'access_api_url'))


def _unauthorized():
    """
    Indicate that authorization is required
    :return:
    """
    return Response("Unauthorized", 401, {"WWW-Authenticate": "Negotiate"})


def _forbidden():
    return Response("Forbidden", 403)


def requires_authentication(function):
    """Determines if the Access Token is valid
    """
    @wraps(function)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", None)
        if not auth:
            return _unauthorized()

        parts = auth.split()

        if parts[0].lower() != "bearer":
            return _unauthorized()
        elif len(parts) == 1:
            return _unauthorized()
        elif len(parts) > 2:
            return _unauthorized()

        token = parts[1]
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        body = {
            'tokenType': 'BEARER',
            'token': str(token)
        }
        url = '%s/tokens' % ACCESS_API_URL
        log.info('API Auth request url=%s body=%s' % (url, body))
        response = requests.post(url=url, data=json.dumps(body), headers=headers, timeout=120)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            log.error('API authentication failed URL=%s : Reason=%s ResponseBody=%s' % (url, response.reason, response.content))
            return _unauthorized()

        respose_dict = json.loads(response.text)
        log.info('API Response data : %s' % respose_dict)

        stack.top.current_user = response.json()
        response = function(*args, **kwargs)
        response = make_response(response)
        return response

    return decorated
