from werkzeug.wrappers import Request, Response
import json
import traceback
import binascii
import os
import time
import requests
import datetime
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, ForeignKey, select, and_
from contextlib import contextmanager
import hashlib
import hmac
from collections import defaultdict

class SimpleWebAPIError(Exception):
    def __init__(self, error_name="SimpleWebAPIError", message="An unknown error occured."):
        self.error_name = error_name
        self.message = message

class SimpleWebAPI:
    def __init__(self):
        self.api_methods = defaultdict(dict)
        self.default_capability = None
        self.get_capabilities = lambda user: None
        self.check_token = lambda token: None
        self.secure_cookies = False
        self.cookie_location = "/"
        self.cookie_name = "token"

        @Request.application
        def application(request):
            if request.method == 'POST' and "application/json" in request.content_type.lower():
                inp = json.loads(request.data.decode('UTF-8'))
                api_version = inp.get("version", 1)
                try:
                    method = inp['method']
                    conf = self.api_methods[method]
                    kwargs = inp.get("kwargs", {});
                    token = None 
                    if "token" in inp:
                        token = inp["token"]
                    elif self.cookie_name in request.cookies:
                        token = request.cookies[self.cookie_name]
                    user = self.check_token(token)
                    capabilities = self.get_capabilities(user)
                    if not capabilities:
                        capabilities = set()
                    details = {
                            "ip":request.remote_addr,
                            "user":user,
                            "capabilities":capabilities,
                            "token":token
                            }
                    if conf["details"]:
                        kwargs["details"] = details
                    require = conf["require"]
                    if require == None or require in capabilities:
                        try:
                            call_result = conf["method"](*inp.get("args", []), **kwargs)
                            res = {"success":True,     
                                   "result":call_result}
                        except SimpleWebAPIError as ex:
                            res = {"success":False,
                                   "error":ex.error_name,
                                   "error_message":ex.message}
                        if details["token"] != token:
                            token = details["token"]
                    else:
                        res = {"success":False,
                               "error":"NotAuthorized",
                               "error_message":"The current user cannot call method '" + method + "'."}
                except Exception as ex:
                    traceback.print_exc()
                    res = {"success":False,
                           "error":"Exception",
                           "error_message":"An exception occured while calling method '" + method + "'."}
                if api_version < 2:
                    if res["success"]:
                        res = res["result"]
                    else:
                        res = {"SimpleWebAPIError":res["error"],
                               "Message":res["error_message"]}
                response_object = Response(json.dumps(res))
                if token:
                    response_object.set_cookie(self.cookie_name, token, expires=datetime.datetime.fromtimestamp(time.time()+31557600),httponly=True,secure=self.secure_cookies, path=self.cookie_location)
                return response_object
            else:
                return Response(json.dumps(list(self.api_methods.keys())))
        
        self.application = application

        @self.add()
        def getMethods():
            return list(self.api_methods.keys())

        @self.add(details=True)
        def getDetails(details):
            return {"capabilities":list(details['capabilities']),
                    "user":details['user']}

        @self.add(details=True)
        def hasCapability(capability, details):
            return capability in details['capabilities']

    def details(self, function):
        """Deprecated decorator to request details."""
        self.api_methods[function.__name__]["details"] = True
        return function

    def add(self, require="DEFAULT_CAP", details=False, name=None):
        """Add a function to the api. (Decorator)
           require: Require a capability to call the function.
           details: Request details of API call, such as user.
           name: Use a different name for the function."""
        # The API used to use this as a "plain" decorator that
        # added the function to the API without any settings.
        if hasattr(require, "__call__"):
            return self.add()(require)

        def add_decorator(function):
            function_name = name or function.__name__
            conf = self.api_methods[function_name]
            conf["method"] = function
            if not "require" in conf:
                if require != "DEFAULT_CAP":
                    conf["require"] = require
                else:
                    conf["require"] = self.default_capability
            if not "details" in conf:
                conf["details"] = details
            return function
        return add_decorator

    def capability(self, require):
        """Deprecated decorator to set capability."""
        def capability_decorator(function):
            self.api_methods[function.__name__]["require"] = require
            return function
        return capability_decorator

    def set_capability_handler(self, function):
        self.get_capabilities = function
        return function

    def set_token_lookup_handler(self, function):
        self.check_token = function
        return function
    def upd_settings(self, settings):
        for key, value in settings.items():
            setattr(self, key, value) 


class EmailSessionManager:
    def __init__(self, api, database):
        self.api = api
        self.print_debug = False
        self.mailgun_key = None
        self.email = None
        self.domain = None
        self.database = database
        self.roles = {}
        self.admin_email = None
        self.admin_user = None

        if not self.check_db_schema():
            self.gen_db_schema()

        self.metadata = MetaData(self.database)
        self.metadata.reflect()
        
        api.set_capability_handler(self.get_capabilities)
        api.set_token_lookup_handler(self.check_token)

        api.add(self.login)
        api.capability(None)(self.login)
        api.details(self.login)
        api.add(self.logoff)
        api.capability(None)(self.logoff)
        api.details(self.logoff)
        api.add(self.logoff_all)
        api.capability(None)(self.logoff_all)
        api.details(self.logoff_all)
        api.add(self.send_otp)
        api.capability(None)(self.send_otp)
        api.details(self.send_otp)

        api.add(self.get_user)
        api.capability("accountmanager")(self.get_user)
        api.add(self.register_user)
        api.capability("accountmanager")(self.register_user)
        api.add(self.set_user_role)
        api.capability("accountmanager")(self.set_user_role)
        api.add(self.list_roles)
        api.capability("accountmanager")(self.list_roles)
        api.add(self.get_all_users)
        api.capability("accountmanager")(self.get_all_users)

    @contextmanager
    def conn(self):
        c = self.database.connect()
        yield c
        c.close()

    def token_hmac(self, token):
        # We use a fixed key here because we aren't using HMAC for signing.
        # The HMAC prevents a user with database access from stealing all active sessions.
        if token == None:
            token = ""
        return hmac.new(b'15d87f6ace820249cb0473df6ce51af6ca0a4721be09ad7fe91d9e644abfcc36',
                bytes(token,'ascii'), hashlib.sha256).hexdigest()

    def gen_token(self, user):
        token = binascii.b2a_hex(os.urandom(32)).decode('UTF-8')
        user_info = self.get_user(user)
        if not user_info:
            self.register_user(user, self.default_role)
            user_info = self.get_user(user)
        tokens = self.metadata.tables['tokens']
        token_crypt = self.token_hmac(token)
        ins = tokens.insert().values(user_id=user_info['id'], token=token_crypt)
        with self.conn() as conn:
            conn.execute(ins)
        return token

    def check_db_schema(self):
        return (self.database.dialect.has_table(self.database, "tokens") and
                self.database.dialect.has_table(self.database, "users") and
                self.database.dialect.has_table(self.database, "challenges"))

    def gen_db_schema(self):
        metadata = MetaData(self.database)
        Table("users", metadata,
              Column('id', Integer, primary_key=True),
              Column('username', String(320)),
              Column('role', String(25)),
        )
        Table("tokens", metadata,
              Column('id', Integer, primary_key=True),
              Column('user_id', None, ForeignKey('users.id')),
              Column('token', String(64), nullable=False),
        )
        Table("challenges", metadata,
              Column('id', Integer, primary_key=True),
              Column('user_id', None, ForeignKey('users.id')),
              Column('otp', String(64), nullable=False),
              Column('expire', Integer, nullable=False),
              Column('token', String(64), nullable=False),
        )
        metadata.create_all(self.database)

    def send_email(self, recipient, subject, text):
        if self.print_debug:
            print("To: "+recipient+"\nSubject: "+subject+"\nMessage: "+text)
        else:
            return requests.post(
            "https://api.mailgun.net/v3/"+self.domain+"/messages",
            auth=("api", self.mailgun_key),
            data={"from": "No Reply <"+self.email+"@"+self.domain+">",
                  "to": [recipient],
                  "subject": subject,
                  "text": text})        

    def get_user(self, username):
        users = self.metadata.tables['users']
        s = select(users.c).where(users.c.username == username)
        with self.conn() as conn:
            result = conn.execute(s)
            row = result.fetchone()
            result.close()
        if not row:
            return False
        else:
            return dict(row)

    def check_token(self, token):
        users = self.metadata.tables['users']
        tokens = self.metadata.tables['tokens']
        token_crypt = self.token_hmac(token)
        s = (select((users.c.username, tokens.c.token))
            .select_from(tokens.join(users))
            .where(tokens.c.token == token_crypt))
        with self.conn() as conn:
            result = conn.execute(s)
            row = result.fetchone()
            result.close()
        if not row:
            return None
        else:
            return row[users.c.username]

    def logoff(self, details):
        token = details['token']
        tokens = self.metadata.tables['tokens']
        token_crypt = self.token_hmac(token)
        with self.conn() as conn:
            conn.execute(tokens.delete().where(tokens.c.token == token_crypt))
        details["token"] = None

    def logoff_all(self, details):
        user = details['user']
        uid = self.get_user(user)['id']
        tokens = self.metadata.tables['tokens']
        with self.conn() as conn:
            conn.execute(tokens.delete().where(tokens.c.user_id == uid))
        details["token"] = None

    def login(self, user, otp, details):
        if self.check_otp(user, otp, details['token']):
            token = self.gen_token(user)
            details["token"] = token
            return {"success":True, "token":token}
        else:
            return {"success":False, "error":"Code is Invalid"}

    def check_otp(self, user, otp, token):
        users = self.metadata.tables['users']
        challenges = self.metadata.tables['challenges']
        otp_crypt = binascii.b2a_hex(hashlib.pbkdf2_hmac('sha256', bytes(otp, 'ascii'), 
            bytes(token, 'ascii'), 100000)).decode('ascii')
        token_crypt = self.token_hmac(token)
        s = (select((challenges.c.token, challenges.c.otp, challenges.c.id))
            .select_from(challenges.join(users))
            .where(and_(challenges.c.token == token_crypt,
                   users.c.username == user,
                   challenges.c.expire > time.time())))
        with self.conn() as conn:
            result = conn.execute(s)
            row = result.fetchone()
            result.close()
            authorized = False
            if row:
                if row[challenges.c.otp] == otp_crypt:
                    authorized = True
                conn.execute(challenges.delete().where(challenges.c.token == token_crypt))
            conn.execute(challenges.delete().where(challenges.c.expire < time.time()))
        return authorized

    def send_otp(self,username,details):
        user_info = self.get_user(username)
        if not user_info:
            self.register_user(username, self.default_role)
            user_info = self.get_user(username)
        challenges = self.metadata.tables['challenges']
        token = binascii.b2a_hex(os.urandom(32)).decode('UTF-8')
        token_crypt = self.token_hmac(token)
        otp = binascii.b2a_hex(os.urandom(3)).decode('UTF-8')
        otp_crypt = binascii.b2a_hex(hashlib.pbkdf2_hmac('sha256', bytes(otp, 'ascii'),
            bytes(token, 'ascii'), 100000)).decode('ascii')
        ins = challenges.insert().values(user_id=user_info['id'],
                                         token=token_crypt,
                                         otp=otp_crypt,
                                         expire=time.time()+600)
        with self.conn() as conn:
            conn.execute(ins)
        details['token'] = token
        self.send_email(username, "Email Login Code",
                        "Please enter the code "+otp+" to login."
                        "\n\nOnly one attempt is permitted. Codes expire"
                        " after 10 minutes. If you are being spammed by"
                        " this address, email "+self.admin_email)
        return token

    def get_capabilities(self, user):
        user_info = self.get_user(user)
        if not user_info:
            return None
        return self.roles.get(user_info["role"])

    def register_user(self, username, role):
        if self.get_user(username):
            return
        users = self.metadata.tables['users']
        ins = users.insert().values(username=username, role=role)
        with self.conn() as conn:
            conn.execute(ins)

    def set_user_role(self, username, role):
        user_info = self.get_user(username)
        if user_info:
            users = self.metadata.tables['users']
            upd = (users.update().values(role=role)
                   .where(users.c.id == user_info['id']))
            with self.conn() as conn:
                conn.execute(upd)

    def recurse_roles(self, roles, role, visited=None):
        if not visited:
            visited = set()
        if not role in roles or roles[role] == None or role in visited:
            return {role}
        visited.add(role)
        flat_roles = {role}
        for role_exp in roles[role]:
            flat_roles.update(self.recurse_roles(roles, role_exp, visited))
        return flat_roles
        
    def upd_settings(self, settings):
        for key, value in settings.items():
            setattr(self, key, value)
        for role in self.roles.keys():
            self.roles[role] = self.recurse_roles(self.roles, role)
        if self.admin_user != "":
            self.register_user(self.admin_user, "root")

    def list_roles(self):
        return list(self.roles.keys())

    def get_all_users(self):
        users = self.metadata.tables['users']
        s = select(users.c)
        with self.conn() as conn:
            result = conn.execute(s)
            response = [dict(x) for x in result]
            result.close()
        return response

