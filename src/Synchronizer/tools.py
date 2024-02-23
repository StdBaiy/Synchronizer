'''
tools functions related to business logic
'''
from operator import truediv
from time import time, sleep
from os import path as ospath, utime, chmod, makedirs
import os
from sys import executable
from threading import Thread, Lock
import re
import fossil_delta
import platform
import hashlib
import secrets
import string
import names
from logging import getLogger, Formatter, handlers, INFO, DEBUG
from datetime import datetime
from OpenSSL import crypto
from watchdog.events import FileSystemEventHandler

def check_ignore(f_path, ignore_list, file_size_limit=None):
    if f_path == '.sync/':
        return True
    elif ospath.isfile(f_path) and file_size_limit and os.stat(f_path).st_size > file_size_limit:
        return True
    for rule in ignore_list:
        if re.match(rule, f_path):
            return True
    return False

def check_edition_exist(dir_path, ed_name):
    dir_path = replace_sep(dir_path)
    if not dir_path.endswith('/'):
        dir_path = dir_path + '/'
    if not ed_name:
        return False
    ed_path = dir_path + ".sync/editions/" + ed_name[:5] + "/" + ed_name[5:]
    return ospath.exists(ed_path)

def check_content_exist(dir_path, sha1):
    # find file contents by sha1 value
    if sha1 == "":
        return True  # empty file will be seen as exist
    content_path = dir_path + ".sync/contents/" + sha1[:2] + "/" + sha1[2:]
    return ospath.exists(content_path)

def parse_msg(msg):
    """
    Parse the message received from the server
    :param msg: The message received from the server
    :return: msg type, token, group token, stream size
    """
    m = msg.split("|", 3)
    if not len(m) == 4:
        raise Exception('parse msg error: ' % (msg))
    dic = {}
    dic['type'] = int(m[0].strip())
    dic['u_token'] = m[1].strip()
    dic['d_token'] = m[2].strip()
    dic['addition'] = m[3].strip()
    return dic

def parse_edition(dir_path, edition_name, ed_content=None):
    # get last edition fts, return empty if not exist
    # if ed_content is not None, parse it directly
    assert edition_name is not None
    if edition_name == "":
        return None
    edition_path = (
        dir_path + ".sync/editions/" + edition_name[:5] + "/" + edition_name[5:]
    )
    if not ed_content and not ospath.exists(edition_path):
        return None
    if not ed_content:
        ed_file = open(edition_path, "rb")
        quote_num, ed_nm, fts = ed_file.read().split("\n".encode(), 2)
        ed_file.close()
    else:
        quote_num, ed_nm, fts = ed_content.split("\n".encode(), 2)
    # get edition file tree stream by decompress delta code (if need)
    if int(quote_num) == 0:
        return int(quote_num), ed_nm.decode(), fts  # int, str, bytes
    else:
        _, _, q_fts = parse_edition(dir_path, ed_nm.decode())
        return int(quote_num), ed_nm.decode(), fossil_delta.apply_delta(q_fts, fts)

def get_last_ed_nm(dir_path):
        # get last edition name
        last_path = dir_path + ".sync/editions/last"
        if not ospath.exists(last_path):
            open(last_path, "a", encoding="utf-8").close()
        with open(last_path, "r", encoding="utf-8") as last_ed_file:
            return last_ed_file.read()

def change_attr(file_path, create_time, last_modify_time, permission):
    """
    change the creation time and modification time of a file/dir
    c_time and m_time are in timestamp in int
    """
    utime(file_path, (int(last_modify_time), int(last_modify_time)))
    chmod(file_path, permission)
    if platform.system() == "Windows":
        try:
            import win32file
            handle = win32file.CreateFile(
                file_path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                win32file.FILE_ATTRIBUTE_NORMAL | win32file.FILE_FLAG_BACKUP_SEMANTICS,
                0,
            )
            # turn to datetime object
            create_time = datetime.fromtimestamp(create_time)
            last_modify_time = datetime.fromtimestamp(last_modify_time)
            win32file.SetFileTime(handle, create_time, last_modify_time, last_modify_time)
            win32file.CloseHandle(handle)
        except Exception as err:
            print(err)

def get_sha(f_path='', type='sha1', content=None):
    if type == 'sha1':
        sha = hashlib.sha1()
    if type == 'sha256':
        sha = hashlib.sha256()
    if type == 'sha512':
        sha = hashlib.sha512()

    # use file in default
    if f_path:
        if ospath.getsize(f_path) == 0:
            return ""
        with open(f_path, "rb") as file:
            while True:
                data = file.read(8192)
                if not data:
                    break
                sha.update(data)
        return sha.hexdigest()

    # if specified the content, then use content
    if content:
        sha.update(content)
        return sha.hexdigest()
    return None
        

def gen_token(length=32):
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for i in range(length))
    return token

def replace_sep(path):
    path = path.replace(r"\\", "/")
    path = path.replace("\\", "/")
    return path

def gen_random_name():
    return names.get_first_name() + '_' + names.get_last_name()
   
def gen_cert(name):
    """
    generate SSL cert and key
    """
    # can look at generated file using openssl:
    ca_cert_file_name = f'cert/{name}.crt'
    ca_key_file_name = f'cert/{name}.key'
    validity_end_in_seconds = 10 * 365 * 24 * 60 * 60 # 10 years
    # openssl x509 -inform pem -in selfsigned.crt -noout -text
    # create a key pair
    ca_key = crypto.PKey()
    ca_key.generate_key(crypto.TYPE_RSA, 4096)
    # create a self-signed cert
    ca_cert = crypto.X509()
    ca_cert.get_subject().CN = "Sync_" + gen_token(8)
    ca_cert.set_serial_number(0)
    ca_cert.gmtime_adj_notBefore(0)
    ca_cert.gmtime_adj_notAfter(validity_end_in_seconds)
    ca_cert.set_issuer(ca_cert.get_subject())
    ca_cert.set_pubkey(ca_key)
    ca_cert.sign(ca_key, "sha512")
    with open(ca_cert_file_name, "w", encoding="utf-8") as cert_file:
        cert_file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert).decode("utf-8"))
    with open(ca_key_file_name, "w", encoding="utf-8") as key_file:
        key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, ca_key).decode("utf-8"))


class timer:
    def __init__(self, interval, func=None, *args, **kwargs):
        assert interval > 0
        self.interval = interval # in seconds
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.cancaled = False
        self.start_time = 0
        self.status = 0 # 0: not started, 1: waiting, 2:running
        self.run_flag = False
        pass

    def __run(self):
        while self.run_flag:
            self.run_flag = False
            self.start_time = time()
            self.status = 1
            while True:
                if self.cancaled:
                    self.status = 0
                    return
                if time() - self.start_time >= self.interval:
                    break
                sleep(0.1)
            self.status = 2
            self.func(*self.args, **self.kwargs)
        self.status = 0


    def start(self):
        if self.status == 0: # not started
            self.cancaled = False
            self.run_flag = True
            Thread(target=self.__run).start()
        elif self.status == 1: # waiting
            self.start_time = time()
            pass
        elif self.status == 2: # running
            return
            self.cancaled = False
            self.run_flag = True # run again
        else:
            raise Exception("Invalid status")


    def is_running(self):
        return self.status == 1
    
    def cancel(self):
        self.cancaled = True
        pass

class MyEventHandler(FileSystemEventHandler):
    """
    this class is used to handle the file system event
    when watchdog observed the change of the managed dir
    it will call the on_any_event function
    that's how sync is triggered
    """

    def __init__(self, interval=0.2, func=None, dir_path="", *args, **kwargs):
        FileSystemEventHandler.__init__(self)
        self.timer = None
        self.event_list = []
        if interval < 0.2:
            interval = 0.2
        self.interval = interval
        self.func = func
        self.dir_path = replace_sep(dir_path)
        if not self.dir_path.endswith("/"):
            self.dir_path += "/"
        self.args = args
        self.kwargs = kwargs
        self.event_mutex = Lock()
        self.timer = timer(self.interval, self.check)
        # add ignore rules
        self.ignore_list = []
        with open(self.dir_path + ".sync/ignore", "r", encoding="utf-8") as ignore_file:
            for rule in ignore_file.readlines():
                rule = rule.strip()
                if rule.startswith("#"):
                    continue
                self.ignore_list.append(rule)

    def on_any_event(self, event):
        rel_path = replace_sep(event.src_path).replace(self.dir_path, "")
        # do not observe the change of .sync dir
        if rel_path == ".sync" or rel_path.startswith(".sync/"):
            return
        for rule in self.ignore_list:
            if re.match(rule, rel_path):
                return
        
        
        with open(self.dir_path + ".sync/editions/changed_flag", "w", encoding="utf-8") as changed_file:
            changed_file.write("1")
        with self.event_mutex:
            self.event_list.append(event)
        status_list = ["not started", "waiting", "running"]
        print(
            datetime.now(),
            status_list[self.timer.status],
            event.event_type,
            event.src_path,
        )
        if self.timer is not None:
            self.timer.start()

    def check(self):
        """
        do the real work
        """
        with self.event_mutex:
            tmp_list = self.event_list.copy()
            self.event_list.clear()
        # for event in tmp_list:
        #     print(event.event_type, event.src_path)
        if self.func:
            self.func(*self.args, **self.kwargs)

def sync_init(dir_path):
    # create .sync folder
    dir_path = replace_sep(dir_path)
    if not dir_path.endswith("/"):
        dir_path = dir_path + "/"
    if not ospath.exists(dir_path + ".sync/editions"):
        makedirs(dir_path + ".sync/editions", exist_ok=True)
    if not ospath.exists(dir_path + ".sync/contents"):
        makedirs(dir_path + ".sync/contents", exist_ok=True)
    # os.makedirs(dir_path + '.sync/encrypt', exist_ok=True)

    if not ospath.exists(dir_path + ".sync/editions/uncommit"):
        open(dir_path + ".sync/editions/uncommit", "a", encoding="utf-8").close()
    if not ospath.exists(dir_path + ".sync/editions/last"):
        open(dir_path + ".sync/editions/last", "a", encoding="utf-8").close()
    if not ospath.exists(dir_path + ".sync/editions/last_sync"):
        open(dir_path + ".sync/editions/last_sync", "a", encoding="utf-8").close()
    if not ospath.exists(dir_path + ".sync/editions/changed_flag"):
        with open(dir_path + ".sync/editions/changed_flag", "w", encoding="utf-8") as changed_file:
            changed_file.write("1")
    # open(dir_path + '.sync/editions/local', 'a').close()
    # open(dir_path + '.sync/encrypt/key', 'a').close()
    # open(dir_path + '.sync/dir_token', 'a').close()
    if not ospath.exists(dir_path + ".sync/ignore"):
        open(dir_path + ".sync/ignore", "a", encoding="utf-8").close()


logger = getLogger()
# # generate a new log file every 3 days
exe_list = ['synchronizer.exe', 'service.exe']
# executable will be '.../python.exe' if start in script mode else one of exe_list\
logfile_path =''
if ospath.basename(executable) in exe_list:
    # exe is in proj_dir/bin
    logfile_path = ospath.join(ospath.dirname(ospath.dirname(executable)), 'log', 'sync.log')
else:
    # __file__ is in proj_dir/src/Synchronizer
    logfile_path = ospath.join(ospath.dirname(ospath.dirname(ospath.dirname(__file__))), 'log', 'sync.log')
handler = handlers.TimedRotatingFileHandler(logfile_path, when="D", interval=3, encoding="utf-8")
formatter = Formatter("%(asctime)s [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(INFO)

def set_writable(path):
    # set a file or dir writable, for deleting them
    if os.path.isfile(path):
        os.chmod(path, 0o666)
        return
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            os.chmod(root, 0o777)            
            for file in files:
                file_path = os.path.join(root, file)
                os.chmod(file_path, 0o666)

def check_username_legitimacy(username):
    # len of username should be in 4-16
    # username can only contain letters, numbers, underline and hyphen
    # and cannot start with number
    if not re.match(r'^(?!^\d)[A-Za-z0-9-_]{4,16}$', username):
        return False
    return True