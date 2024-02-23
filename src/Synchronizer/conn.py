from operator import truediv
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SHUT_RDWR
import ssl
from time import sleep

from Synchronizer.params import global_var
from .tools import logger

# msg [type]|[user token]|[dir token]|[next data size or other info]
MSG_FORMAT = "%3s|%32s|%32s|%64s"
MSG_LEN = 134  # 144 is the encrypted length

UPLOAD_REQUEST = 0
DOWNLOAD_REQUEST = 1
UPLOAD_SUCCESS = 2
UPLOAD_FAILED = 3
DOWNLOAD_SUCCESS = 4
DOWNLOAD_FAILED = 5
ALLOW_UPLOAD = 6
REFUSE_UPLOAD = 7
ALLOW_DOWNLOAD = 8
REFUSE_DOWNLOAD = 9
SEND_FILE_BLOCK = 10
RECV_FILE_BLOCK_SUCCESS = 11
RECV_FILE_BLOCK_FAILED = 12

SYNC_REQUEST = 13
SYNC_SUCCESS = 14
SYNC_FAILED = 15

REFUSE = 16
TIME_STAMP = 17

LONG_CONN = 18
UPDATE = 19

REGISTER_USER = 20
REGISTER_DIR = 21
JOIN_DIR = 22
REGISTER_SUCCESS = 23
REGISTER_FAILED = 24
JOIN_SUCCESS = 25
JOIN_FAILED = 26

MODIFY_USER = 27
MOFIFY_DIR = 28
MODIFY_SUCCESS = 29
MODIFY_FAILED = 30

ADD_DIR = 31
ADD_DIR_SUCCESS = 32
ADD_DIR_FAILED = 33

VERIFY_REQUEST = 34
VERIFY_SUCCESS = 35
VERIFY_FAILED = 36


def synchronizer_listen(addr, port, listen_num=128):
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    server_socket.bind((addr, port))
    server_socket.listen(listen_num)
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="cert/server.crt", keyfile="cert/server.key")
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile="cert/client.crt")
    # return server_socket, context
    while global_var.listening:
        try:
            client_socket, _ = server_socket.accept()
            conn = context.wrap_socket(client_socket)
            yield conn
        except:
            conn.close()

    
def verification_listen(addr, port, listen_num=128):
    ver_sock = socket(AF_INET, SOCK_STREAM)
    ver_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    ver_sock.bind((addr, port))
    ver_sock.listen(listen_num)
    while global_var.listening:
        try:
            client_sock, _ = ver_sock.accept()
            conn = ssl.wrap_socket(client_sock, keyfile='cert/server.key', certfile='cert/server.crt', server_side=True)
            yield conn
        except:
            conn.close()



def tcp_ssl_connect(addr, port):
    """
    connect to server with ssl
    """
    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.load_cert_chain(certfile="cert/client_verify.crt", keyfile="cert/client_verify.key")
        context.load_verify_locations(cafile="cert/server_verify.crt")
        # wrap the socket with SSL
        conn_secure = context.wrap_socket(sock)

        conn_secure.connect((addr, port))
        return conn_secure
    except Exception as err:
        logger.error("connect %s:%d failed, %s", addr, port, err)
        return None
        
def my_recv(sock, left_len, seg_size=32 * 1024 * 1024):
    # assert left_len <= BLOCK_SIZE, 'The length of data to receive is too large'
    try:
        data = b""
        while left_len > 0:
            if left_len > seg_size:
                new_data = sock.recv(seg_size)
            else:
                new_data = sock.recv(left_len)
            if not new_data:
                return b""
            data = data + new_data
            left_len = left_len - len(new_data)
        return data
    except Exception as e:
        print("error when receiving data")
        print(e)
        return b""
    
def shutdown_conn(sock, timeout):
    """
    assure the socket can be closed in time
    """
    if sock.fileno() == -1:
        return
    sleep(timeout)
    if sock.fileno() != -1:
        sock.shutdown(SHUT_RDWR)
        sock.close()
        logger.error("connection didn't finished in %d seconds, timeout", timeout)

def get_sock(addr, port):
    """
    return a socket connected to server
    max num is 1, if failed to connect, return None
    """
    # if sync.server_sock:
    #     sync.server_sock.close()
    if not addr or not port:
        return None
    return tcp_ssl_connect(addr, port)

def get_long_conn(addr, port, callback):
      pass

def handle_long_conn():
    pass

def send_msg(sock, type, u_token='', d_token='', addition=''):
    msg = (MSG_FORMAT % (type, u_token, d_token, addition)).encode()
    sock.sendall(msg)
    pass