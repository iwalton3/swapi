#!/usr/bin/env python3
from sqlalchemy import create_engine, MetaData, select
import json
from contextlib import contextmanager
import hmac
import hashlib

conf = json.load(open("/etc/swa-conf.json"))
database = create_engine(conf["database"], pool_recycle=3600)

metadata = MetaData(database)
metadata.reflect()

@contextmanager
def conn():
    c = database.connect()
    yield c
    c.close()

tokens = metadata.tables['tokens']
s = select((tokens.c.id, tokens.c.token))

with conn() as conn:
    result = conn.execute(s)
    for row in result:
        token_crypt = hmac.new(b'15d87f6ace820249cb0473df6ce51af6ca0a4721be09ad7fe91d9e644abfcc36',
                bytes(row[tokens.c.token],'ascii'), hashlib.sha256).hexdigest()
        upd = (tokens.update().values(token=token_crypt)
                   .where(tokens.c.id == row[tokens.c.id]))
        conn.execute(upd)

