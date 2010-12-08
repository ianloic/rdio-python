'''A Python library for accessing the Rdio REST API with OAuth'''
import sys, os
# depends on oauth2 from https://github.com/simplegeo/python-oauth2
import oauth2 as oauth
from cgi import parse_qsl
import urllib, logging
try:
  from django.utils import simplejson as json
except:
  import json

DEV = False
AUTH = True

class RdioMethod(object):
    def __init__(self, name, rdio):
        self.name = name
        self.rdio = rdio

    def __call__(self, **args):
        return self.rdio.call(self.name, **args)

class RdioException(BaseException):
    pass

class RdioProtocolException(RdioException):
    def __init__(self, code, content):
        RdioException.__init__(self)
        self.code = code
        self.content = content
    def __str__(self):
        return 'RdioProtocolException %s: %s' % (self.code, self.content)    

class RdioAPIException(RdioException):
    def __init__(self, message):
        RdioException.__init__(self, message)


class Rdio(object):
    if DEV:
        REQUEST_TOKEN='http://rdio-dev.api.mashery.com/oauth/request_token'
        ACCESS_TOKEN='http://rdio-dev.api.mashery.com/oauth/access_token'
        if AUTH:
            API='http://rdio-dev.api.mashery.com/1/'
        else:
            API='http://localhost:8000/api/1/'
    else:
        REQUEST_TOKEN='http://api.rdio.com/oauth/request_token'
        ACCESS_TOKEN='http://api.rdio.com/oauth/access_token'
        API='http://api.rdio.com/1/'
    def __init__(self, consumer_token, consumer_secret, data_store):
        self.__consumer = oauth.Consumer(consumer_token, consumer_secret)
        self.__data_store = data_store

    @property
    def authenticating(self):
        return self.__data_store.has_key('request_token') and self.__data_store['request_token']

    @property
    def authenticated(self):
        return self.__data_store.has_key('access_token') and self.__data_store['access_token']


    def begin_authentication(self, callback_url):
        assert not self.authenticating and not self.authenticated

        resp, content = self.__client().request(Rdio.REQUEST_TOKEN, 'POST',
                                       urllib.urlencode({'oauth_callback':callback_url}))
        if resp['status'] != '200':
            raise RdioProtocolException(resp['status'], content)
        request_token = dict(parse_qsl(content))
        self.__data_store['request_token'] = request_token
        return (request_token['login_url']+'?oauth_token='+request_token['oauth_token'])


    def complete_authentication(self, oauth_verifier):
        assert self.authenticating and not self.authenticated

        client = self.__client(oauth_verifier)
        resp, content = client.request(Rdio.ACCESS_TOKEN, "POST")
        if resp['status'] != '200':
            raise RdioProtocolException(resp['status'], content)
        access_token = dict(parse_qsl(content))
        self.__data_store['access_token'] = access_token
        del self.__data_store['request_token']


    def logout(self):
        if self.authenticating:
            del self.__data_store['request_token']
        if self.authenticated:
            del self.__data_store['access_token']


    def __client(self, oauth_verifier=None):
        token = None
        if self.authenticated:
            at = self.__data_store['access_token']
            token = oauth.Token(at['oauth_token'], at['oauth_token_secret'])
        elif self.authenticating:
            rt = self.__data_store['request_token']
            token = oauth.Token(rt['oauth_token'], rt['oauth_token_secret'])
        if token is not None and oauth_verifier is not None:
            token.set_verifier(oauth_verifier)
        return oauth.Client(self.__consumer, token)


    def call(self, method, **args):
        '''Call a method on the Rdio service and return the result as a
        Python object. If there's an error then throw an appropriate
        exception.'''
        resp, content = self.call_raw(method, **args)
        if resp['status'] != '200':
            raise RdioProtocolException(resp['status'], content)
        response = json.loads(content)
        if response['status'] == 'ok':
            return response['result']
        else:
            raise RdioAPIException(response['message'])

        
    def call_raw(self, method, **args):
        '''Call a method on the Rdio service and return the raw HTTP result,
        a response object and the content object. See the httplib2 request
        method for examples'''
        args['method'] = method
        client = self.__client()
        return client.request(Rdio.API, 'POST', urllib.urlencode(args))

        
    def __getattr__(self, name):
        return RdioMethod(name, self)
