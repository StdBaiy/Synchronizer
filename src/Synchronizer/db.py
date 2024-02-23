'''
this module support database operation
mainly used to store and get user info and dir info
'''

import sqlite3
from os import path as ospath
from .params import global_var

ENABLE_FOREIGN_KEYS = "PRAGMA foreign_keys = ON;"

CREATE_USER_TABLE = """
CREATE TABLE IF NOT EXISTS user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  token TEXT NOT NULL,
  registered INTEGER
);"""
CREATE_DIR_TABLE = """
CREATE TABLE IF NOT EXISTS dir (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL,
  path TEXT NOT NULL,
  registered INTEGER
);"""
CREATE_USER_DIR_TABLE = """
CREATE TABLE IF NOT EXISTS user_dir (
  user_id INTEGER,
  dir_id INTEGER,
  PRIMARY KEY (user_id, dir_id),
  FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
  FOREIGN KEY (dir_id) REFERENCES dir(id) ON DELETE CASCADE
);"""

CREATE_ENCRYPT_TABLE = """
CREATE TABLE IF NOT EXISTS encrypt (

);"""

CREATE_ME_TABLE = """
CREATE TABLE IF NOT EXISTS me (
  user_id INTEGER,
  FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);
"""

CREATE_TIME_TABLE = """
CREATE TABLE IF NOT EXISTS time (
  dir_id INTEGER,
  edition_name TEXT NOT NULL UNIQUE,
  commit_time DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'now')),
  FOREIGN KEY (dir_id) REFERENCES dir(id) ON DELETE CASCADE
);
"""

def create_tables(type="client"):
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    c.execute(CREATE_USER_TABLE)
    c.execute(CREATE_DIR_TABLE)
    c.execute(CREATE_USER_DIR_TABLE)
    c.execute(CREATE_ME_TABLE)
    c.execute(CREATE_TIME_TABLE)
    conn.commit()
    conn.close()

# notice that type param is only for test
def __conn_db(type="client"):
    if global_var.test:
        if type == "server":
            return sqlite3.connect("db/test_server.db")
        elif type == "client":
            return sqlite3.connect("db/test_client.db")
        else:
            return None
    return sqlite3.connect("db/sync.db")

def insert_user(name, token, registered=1, type="client"):
    if not name or not token:
        return False
    if check_user_exist(name=name, type="server") or check_user_exist(token=token, type="server"):
        return False
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    c.execute("INSERT INTO user (name, token, registered) VALUES (?, ?, ?)", (name, token, registered,))
    conn.commit()
    conn.close()
    return True

def update_user_info(user_id, name=None, token=None, registered=None, type="client"):
    if name is None and token is None and registered is None:
        return False
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    c.execute('SELECT name, token, registered FROM user WHERE id = ?', (user_id,))
    res = c.fetchone()
    if res is None: # query failed
        return False
    origin_name, origin_token, origin_registered = res
    name = name if name is not None else origin_name
    token = token if token is not None else origin_token
    registered = registered if registered is not None else origin_registered
    c.execute('UPDATE user SET name=?, token=?, registered=? WHERE id = ?', (name, token, registered, user_id,))
    conn.commit()
    conn.close()
    return True

def check_user_exist(token=None, name=None, id=None, type="client"):
    if token is None and name is None and id is None:
        return False
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    if name:
        c.execute('SELECT name, token, id FROM user WHERE name = ?', (name,))
    elif token:
        c.execute('SELECT name, token, id FROM user WHERE token = ?', (token,))
    else:
        c.execute('SELECT name, token, id FROM user WHERE id = ?', (id,))
    result = c.fetchone()
    if result is None:
        conn.close()
        return False
    if name and result[0] != name:
        return False
    if token and result[1] != token:
        return False
    if id and result[2] != id:
        return False
    return True


def insert_dir(token, path, description='', registered=1, type="client"):
    if token is None or path is None:
        return False
    if check_dir_exist(token=token, type=type) or check_dir_exist(path=path, type=type):
        return False
    path = ospath.abspath(path)
    drive, rest = ospath.splitdrive(path) 
    path = drive.upper() + rest # turn drive letter to uppercase
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    c.execute("INSERT INTO dir (token, path, description, registered) VALUES (?, ?, ?, ?)", (token, path, description, registered))
    conn.commit()
    conn.close()
    return True

def update_dir_info(dir_id, path=None, token=None, registered=None, description=None, type="client"):
    if path is None and token is None and registered is None and description is None:
        return False
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    c.execute('SELECT path, token, description, registered FROM dir WHERE id = ?', (dir_id,))
    res = c.fetchone()
    if res is None: # query failed
        return False
    origin_name, origin_token, origin_description, origin_registered = res
    path = path if path is not None else origin_name
    token = token if token is not None else origin_token
    registered = registered if registered is not None else origin_registered
    description = description if description is not None else origin_description
    c.execute('UPDATE dir SET path=?, token=?, registered=?, description=? WHERE id = ?', (path, token, registered, description, dir_id,))
    conn.commit()
    conn.close()
    return True

def check_dir_exist(token=None, path=None, id=None, type="client"):
    if token is None and path is None and id is None:
        return False
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    if token:
        c.execute('SELECT token, path, id FROM dir WHERE token = ?', (token,))
    elif path:
        path = ospath.abspath(path)
        drive, rest = ospath.splitdrive(path) 
        path = drive.upper() + rest # turn drive letter to uppercase
        c.execute('SELECT token, path, id FROM dir WHERE path = ?', (path,))
    else:
        c.execute('SELECT token, path, id FROM dir WHERE id = ?', (id,))
    result = c.fetchone()
    if result is None:
        conn.close()
        return False
    if token and result[0] != token:
        return False
    if path and result[1] != path:
        return False
    if id and result[2] != id:
        return False
    return True


def create_me(name, type="client"):
    # create me from existed user
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    c.execute("SELECT id FROM user WHERE name = ?", (name,))
    res = c.fetchone()
    if res is None:
        return False
    user_id = res[0]
    c.execute('DELETE FROM me') # clear me table
    c.execute("INSERT INTO me (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    return True


def get_me_info(type="client"):
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute("select user_id from me")
    res = c.fetchone()
    if res is None: # no me info
        return None
    user_id = res[0]
    return  get_user_info(id=user_id, type=type)


def insert_user_dir(user_id, dir_id, type="client"):
    if not check_user_exist(id=user_id, type=type) or not check_dir_exist(id=dir_id, type=type):
        return False
    if check_user_dir_exist(user_id, dir_id, type=type):
        return True
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    c.execute("INSERT INTO user_dir (user_id, dir_id) VALUES (?, ?)", (user_id, dir_id,))
    conn.commit()
    conn.close()
    return True

def check_user_dir_exist(user_id, dir_id, type="client"):
    if user_id is None or dir_id is None:
        return False
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    c.execute("select * from user_dir where user_id = ? and dir_id = ?", (user_id, dir_id,))
    res = c.fetchone()
    conn.close()
    return True if res else False



# def insert_user_dir_by_name(user_name, dir_token):
#     conn = __conn_db(type)
#     c = conn.cursor()
#     c.execute(ENABLE_FOREIGN_KEYS)
#     c.execute("SELECT id FROM user WHERE name = ?", (user_name,))
#     user_id = c.fetchone()[0]
#     c.execute("SELECT id FROM dir WHERE token = ?", (dir_token,))
#     dir_id = c.fetchone()[0]
#     c.execute(
#         "INSERT INTO user_dir (user_id, dir_id) VALUES (?, ?)",
#         (
#             user_id,
#             dir_id,
#         ),
#     )
#     conn.commit()
#     conn.close()

def get_user_info(token=None, name=None, id=None, type="client"):
    if not check_user_exist(token, name, id, type=type):
        return None
    conn = __conn_db(type)
    c = conn.cursor()
    if token:
        c.execute("SELECT name, token, registered, id FROM user WHERE token = ?", (token,))
    elif name:
        c.execute("SELECT name, token, registered, id FROM user WHERE name = ?", (name,))
    else:
        c.execute("SELECT name, token, registered, id FROM user WHERE id = ?", (id,))
    result = c.fetchone()
    conn.close()
    dic = {}
    dic['name'] = result[0]
    dic['token'] = result[1]
    dic['registered'] = result[2]
    dic['id'] = result[3]
    return dic


def get_dir_info(token=None, path=None, id=None, type="client"):
    if token is None and path is None and id is None:
        return None
    conn = __conn_db(type)
    c = conn.cursor()
    if token:
        c.execute("SELECT path, token, description, id, registered FROM dir WHERE token = ?", (token,))
    elif path:
        path = ospath.abspath(path)
        drive, rest = ospath.splitdrive(path) 
        path = drive.upper() + rest # turn drive letter to uppercase
        c.execute("SELECT path, token, description, id, registered FROM dir WHERE path = ?", (path,))
    else:
        c.execute("SELECT path, token, description, id, registered FROM dir WHERE id = ?", (id,))
    result = c.fetchone()
    conn.close()
    dic = {}
    dic['path'] = result[0]
    dic['token'] = result[1]
    dic['description'] = result[2]
    dic['id'] = result[3]
    dic['registered'] = result[4]
    return dic


def filter_ed_by_time(dir_id, time, type="client"):
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute("SELECT edition_name from time where dir_id = ? and commit_time > ?", (dir_id, time,))
    result = c.fetchall()
    conn.close()
    return result


def insert_edition(dir_id, name, timestamp=None, type="client"):
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(ENABLE_FOREIGN_KEYS)
    c.execute('SELECT edition_name FROM time WHERE edition_name = ?', (name,))
    result = c.fetchone()
    if result:
        conn.close()
        return False
    if timestamp is None:
        c.execute("INSERT INTO time (dir_id, edition_name) VALUES (?, ?)", (dir_id, name,))
    else:
        c.execute("INSERT INTO time (dir_id, edition_name, commit_time) VALUES (?, ?, ?)", (dir_id, name, timestamp,))
    conn.commit()
    conn.close()
    return True


def get_commit_time(ed_name, type="client"):
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute("SELECT commit_time FROM time WHERE edition_name = ?", (ed_name,))
    result = c.fetchone()[0]
    conn.close()
    return result

def clear_associations(user_id, dir_ids=[], type="client"):
    # clear all associations that dir_id is not in dir_ids
    if not check_user_exist(id=user_id, type=type):
        return False
    conn = __conn_db(type)
    c = conn.cursor()
    if len(dir_ids) == 0:
        c.execute("DELETE FROM user_dir WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    para = [user_id]
    para.extend(dir_ids)
    c.execute("DELETE FROM user_dir WHERE user_id = ? and dir_id NOT IN ({})" \
    .format(','.join('?' * len(dir_ids))), para)
    conn.commit()
    conn.close()
    return True

def query(table_name, type="client"):
    # this function is only for test !!!
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute("SELECT * FROM %s" % (table_name))
    result = c.fetchall()
    conn.close()
    return result

def execute(sql, type="client"):
    conn = __conn_db(type)
    c = conn.cursor()
    c.execute(sql)
    conn.commit()
    conn.close()