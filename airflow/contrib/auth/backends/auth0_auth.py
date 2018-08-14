# Copyright 2018 Prabodha Rodrigo (prabodha.rodrigo@roames.com.au)
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import flask_login

# Need to expose these downstream
# pylint: disable=unused-import
from flask_login import (current_user,
                         logout_user,
                         login_required,
                         login_user)
# pylint: enable=unused-import

from flask import url_for, redirect, request

from flask_oauthlib.client import OAuth

from airflow import models, configuration
from airflow.utils.db import provide_session
from airflow.utils.log.logging_mixin import LoggingMixin

log = LoggingMixin().log


def get_config_param(param):
    return str(configuration.conf.get('auth0', param))


class Auth0User(models.User):

    def __init__(self, user):
        self.user = user

    def is_active(self):
        '''Required by flask_login'''
        return True

    def is_authenticated(self):
        '''Required by flask_login'''
        return True

    def is_anonymous(self):
        '''Required by flask_login'''
        return False

    def get_id(self):
        '''Returns the current user id as required by flask_login'''
        return self.user.get_id()

    def data_profiling(self):
        '''Provides access to data profiling tools'''
        return True

    def is_superuser(self):
        '''Access all the things'''
        return True


class AuthenticationError(Exception):
    pass


class Auth0AuthBackend(object):

    def __init__(self):
        self.login_manager = flask_login.LoginManager()
        self.login_manager.login_view = 'airflow.login'
        self.flask_app = None
        self.auth0_oauth = None
        self.api_rev = None
        self.auth0_domain = get_config_param('domain')

    def init_app(self, flask_app):
        self.flask_app = flask_app

        self.login_manager.init_app(self.flask_app)

        self.auth0_oauth = OAuth(self.flask_app).remote_app(
            'auth0',
            consumer_key=get_config_param('client_id'),
            consumer_secret=get_config_param('client_secret'),
            base_url='https://%s/' % self.auth0_domain,
            request_token_url=None,  # Always None in OAuth2
            access_token_method='POST',
            access_token_url='https://%s/oauth/token' % self.auth0_domain,
            authorize_url='https://%s/authorize' % self.auth0_domain,
            request_token_params={'scope': ['openid profile', 'email']})

        self.login_manager.user_loader(self.load_user)

        self.flask_app.add_url_rule(get_config_param('auth0_callback_route'),
                                    'auth0_callback',
                                    self.auth0_callback)

    def login(self, request):
        log.debug('Redirecting user to Auth0 login')
        return self.auth0_oauth.authorize(callback=url_for(
            'auth0_callback',
            _external=True,
            _scheme=get_config_param('auth0_callback_scheme')),
            state=request.args.get('next') or request.referrer or None)

    @provide_session
    def load_user(self, userid, session=None):
        if not userid or userid == 'None':
            return None

        user = session.query(models.User).filter(
            models.User.id == int(userid)).first()
        return Auth0User(user)

    @provide_session
    def auth0_callback(self, session=None):
        log.debug('Auth0 callback called')

        next_url = request.args.get('state') or url_for('admin.index')

        resp = self.auth0_oauth.authorized_response()

        try:
            if resp is None:
                raise AuthenticationError(
                    'Null response from Auth0, denying access.'
                )

            user_info_url = 'https://%s/userinfo' % self.auth0_domain

            resp = self.auth0_oauth.get(user_info_url, token=(resp['access_token'], ''))

            if not resp or resp.status != 200:
                raise AuthenticationError(
                    'Failed to fetch user profile, status ({0})'.format(
                        resp.status if resp else 'None'))

            username = resp.data['name']
            email = resp.data['email']

        except AuthenticationError:
            return redirect(url_for('airflow.noaccess'))

        user = session.query(models.User).filter(
            models.User.username == username).first()

        if not user:
            user = models.User(
                username=username,
                email=email,
                is_superuser=False)

        session.merge(user)
        session.commit()
        login_user(Auth0User(user))
        session.commit()

        return redirect(next_url)


login_manager = Auth0AuthBackend()


def login(self, request):
    return login_manager.login(request)
