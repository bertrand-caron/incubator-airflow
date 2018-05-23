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

from airflow import configuration as conf

from flask import Response
from flask import _request_ctx_stack as stack
from flask import make_response
from flask import request
from functools import wraps

AUTH0_DOMAIN = None
client_auth = None


log = LoggingMixin().log


def get_config_param(param):
    return str(conf.get('auth0', param))


def init_app(app):
    global AUTH0_DOMAIN

    AUTH0_DOMAIN = get_config_param('domain')


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
        url = "https://%s/tokeninfo?id_token=%s" % (AUTH0_DOMAIN, token)
        response = requests.get(url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            return _unauthorized()

        stack.top.current_user = response.json()
        response = function(*args, **kwargs)
        response = make_response(response)
        return response

    return decorated
