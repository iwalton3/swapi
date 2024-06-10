import binascii
import os
import time
import requests
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, ForeignKey, select, and_, inspect, update
from contextlib import contextmanager
import hashlib
import hmac
from swa import ClassAPI

class EmailSessionManager:
    capi = ClassAPI()

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

        self.metadata = MetaData()
        self.metadata.reflect(self.database)

        api.set_capability_handler(self.get_capabilities)
        api.set_token_lookup_handler(self.check_token)

        EmailSessionManager.capi.commit(self, api)

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
        with self.database.begin() as conn:
            conn.execute(ins)
        return token

    def check_db_schema(self):
        return (inspect(self.database).has_table("tokens") and
            inspect(self.database).has_table("users") and
            inspect(self.database).has_table("challenges"))

    def gen_db_schema(self):
        metadata = MetaData()
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

    @capi.add(require="accountmanager")
    def get_user(self, username):
        users = self.metadata.tables['users']
        s = select(users.c).where(users.c.username == username)
        with self.database.begin() as conn:
            result = conn.execute(s)
            row = result.fetchone()
            result.close()
        if not row:
            return False
        else:
            return row._mapping

    def check_token(self, token):
        users = self.metadata.tables['users']
        tokens = self.metadata.tables['tokens']
        token_crypt = self.token_hmac(token)
        s = (select(users.c.username, tokens.c.token)
            .select_from(tokens.join(users))
            .where(tokens.c.token == token_crypt))
        with self.database.begin() as conn:
            result = conn.execute(s)
            row = result.fetchone()
            result.close()
        if not row:
            return None
        else:
            return row._mapping[users.c.username]

    @capi.add(require=None, details=True)
    def logoff(self, details):
        token = details['token']
        tokens = self.metadata.tables['tokens']
        token_crypt = self.token_hmac(token)
        with self.database.begin() as conn:
            conn.execute(tokens.delete().where(tokens.c.token == token_crypt))
        details["token"] = None

    @capi.add(require=None, details=True)
    def logoff_all(self, details):
        user = details['user']
        uid = self.get_user(user)['id']
        tokens = self.metadata.tables['tokens']
        with self.database.begin() as conn:
            conn.execute(tokens.delete().where(tokens.c.user_id == uid))
        details["token"] = None

    @capi.add(require=None, details=True)
    def login(self, user, otp, details):
        user = user.lower()
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
        s = (select(challenges.c.token, challenges.c.otp, challenges.c.id)
            .select_from(challenges.join(users))
            .where(and_(challenges.c.token == token_crypt,
                   users.c.username == user,
                   challenges.c.expire > time.time())))
        with self.database.begin() as conn:
            result = conn.execute(s)
            row = result.fetchone()
            result.close()
            authorized = False
            if row:
                if row._mapping[challenges.c.otp] == otp_crypt:
                    authorized = True
                conn.execute(challenges.delete().where(challenges.c.token == token_crypt))
            conn.execute(challenges.delete().where(challenges.c.expire < time.time()))
        return authorized

    @capi.add(require=None, details=True)
    def send_otp(self,username,details):
        username = username.lower()
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
        with self.database.begin() as conn:
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

    @capi.add(require="accountmanager")
    def register_user(self, username, role):
        username = username.lower()
        if self.get_user(username) or not username:
            return
        users = self.metadata.tables['users']
        ins = users.insert().values(username=username, role=role)
        with self.database.begin() as conn:
            conn.execute(ins)

    @capi.add(require="accountmanager")
    def set_user_role(self, username, role):
        user_info = self.get_user(username)
        if user_info:
            users = self.metadata.tables['users']
            upd = (update(users)
                   .where(users.c.id == user_info['id'])
                   .values(role=role))
            with self.database.begin() as conn:
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

    @capi.add(require="accountmanager")
    def list_roles(self):
        return list(self.roles.keys())

    @capi.add(require="accountmanager")
    def get_all_users(self):
        users = self.metadata.tables['users']
        s = select(users.c)
        with self.database.begin() as conn:
            result = conn.execute(s)
            response = [dict(x._mapping) for x in result]
            result.close()
        return response

