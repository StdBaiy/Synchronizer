from operator import truediv
import time
import ssl
import platform
from threading import Thread
import traceback
from concurrent.futures import ThreadPoolExecutor
from no_delay_observer import Observer
from .conn import *
from .edition import revert_edition, create_edition, commit_edition, sync_edition
from .tools import check_username_legitimacy, logger, replace_sep, parse_msg, sync_init, gen_token, MyEventHandler
from .transfer import handle_upload, handle_download
from .security import self_check
from .params import config, global_var
from .msg import handle_reg_dir, handle_add_dir, handle_verify
from .db import *

pool = ThreadPoolExecutor(8)

def recv_msg(client_sock):
    """
    try to recv msg from another node
    do different things according to msg type
    """
    # must finish before timeout, this is to protect server
    # tmr = Timer(conn_timeout, shutdown_conn, args=(client_socket,))
    # tmr.start()
    try:
        first_msg = my_recv(client_sock, MSG_LEN)
        msg_info = parse_msg(first_msg.decode())
        msg_type = msg_info['type']
        user_token = msg_info['u_token']
        addition = msg_info['addition']
        user_name = get_user_info(token=user_token, type="server")['name'] if check_user_exist(token=user_token, type="server") else "new register user"
        result = False
        if msg_type == UPLOAD_REQUEST:
            result, d_path, ed_name = handle_upload(first_msg, client_sock)
            if config.always_cover:
                revert_edition(d_path, ed_name)
        elif msg_type == DOWNLOAD_REQUEST:
            result = handle_download(first_msg, client_sock)
        elif msg_type == LONG_CONN:
            set_keep_alive(client_sock)
            # add into conn pool
            # currently using map, may improving later
            if user_token in global_var.conn_pool and global_var.conn_pool[user_token]:
                global_var.conn_pool[user_token].close()
            global_var.conn_pool[user_token] = client_sock
            logger.info("+++ '%s' long connection established\n", user_name)
            result = True
        elif msg_type == JOIN_DIR:
            logger.info("recv join dir request from '%s'", user_name)
            result = True
        elif msg_type == REGISTER_DIR:
            result = handle_reg_dir(client_sock, first_msg)
        elif msg_type == REGISTER_USER:
            logger.info("recv register user request")
            user_name = addition
            assert user_name

            if not check_username_legitimacy(user_name):
                send_msg(client_sock, REGISTER_FAILED)
                

            # name already exist, can't reg once more
            if check_user_exist(name=user_name, type="server"):
                logger.error("user name '%s' already exist", user_name)
                send_msg(client_sock, REGISTER_FAILED)
            else:
                for try_time in range(5):
                    new_u_token = gen_token(32)
                    if check_user_exist(token=new_u_token, type="server") or check_user_exist(name=user_name, type="server"):
                        continue
                    if insert_user(user_name, new_u_token, registered=1, type="server"):
                        break
                logger.info("new user register ok with name '%s' and token '%s'", user_name, new_u_token)
                send_msg(client_sock, REGISTER_SUCCESS, addition=new_u_token)
                result = True
        elif msg_type == MODIFY_USER:
            new_name = addition
            if not check_user_exist(token=user_token, type="server"):
                logger.error("modify user failed, no such user token")
                send_msg(client_sock, MODIFY_FAILED)
            elif new_name: # try to modify name
                # check validation, TODO
                if check_user_exist(name=new_name, type="server"):
                    logger.error("modify user failed, name '%s' already exists", new_name)
                    send_msg(client_sock, MODIFY_FAILED)
                else:
                    u_id = get_user_info(token=user_token, type="server")['id']
                    if not update_user_info(u_id, new_name, user_token, registered=1, type="server"):
                        logger.error("modify user failed, update error")
                        send_msg(client_sock, MODIFY_FAILED)
                    else:
                        logger.info("modify user ok, new name '%s'", new_name)
                        send_msg(client_sock, MODIFY_SUCCESS)
            else: # try to modify token
                for try_time in range(5):
                    new_u_token = gen_token()
                    if not check_user_exist(token=new_u_token, type="server"):
                        break
                u_id = get_user_info(token=user_token, type="server")['id']
                if update_user_info(u_id, token=new_u_token, type="server"):
                    logger.info("modify user ok, new token '%s'", new_u_token)
                    send_msg(client_sock, MODIFY_SUCCESS, addition=new_u_token)
                else:
                    logger.error("modify user failed, update error")
                    send_msg(client_sock, MODIFY_FAILED)
        elif msg_type == ADD_DIR:
            res = handle_add_dir(client_sock, first_msg)
        # if tmr: tmr.cancel()
        if msg_type != LONG_CONN:
            client_sock.close()
        return result
    except Exception as err:
        logger.error(traceback.format_exc())
        client_sock.close()
        return False

def __start_server():
    # server_socket, context = synchronizer_listen(config.server_addr, config.server_port, config.listen_num)
    # if global_var.server_sock:
    #     global_var.server_sock.close()
    # global_var.server_sock = server_socket
    gen_sock = synchronizer_listen(config.server_addr, config.server_port, config.listen_num)
    while True:
        try:
            conn = next(gen_sock)
            pool.submit(recv_msg, conn)
        except:
            break

def start_server():
    """
    start server in a new thread
    and return the thread
    """
    global_var.node = 'server'
    if not self_check():
        logger.error('failed to pass self-check')
        exit(-1)
    server_thread = Thread(target=__start_server)
    server_thread.start()
    
    logger.info("=================================")
    logger.info(" synchronzer start at port %d", config.server_port)
    logger.info("=================================")
    if config.allow_verification:
        # listen for verification
        gen_versock = verification_listen(config.server_addr, config.verify_port, config.listen_num)
        while True:
            conn = next(gen_versock)
            pool.submit(handle_verify, conn)
    server_thread.join()

def close_server():
    if global_var.server_sock:
        global_var.server_sock.close()

def __scan():
    """
    try to create and commit edition
    1s sleep to keep every edition has at least 1s interval
    """
    # sync.parse_config()
    for dir_path in config.managed_dirs:
        try:
            # print(datetime.now(), "scan dir: " + dir_path)
            # self.sync_init(dir_path)
            create_edition(dir_path)
            commit_edition(dir_path)
            # time.sleep(1)
            # print(datetime.now(), 'scan done')
        except Exception:
            logger.error(traceback.format_exc())

def __bindcallback(sock, callback, *args, **kwargs):
    t = Thread(target=callback, args=(sock, *args), kwargs=kwargs)
    t.start()
    return t

def set_keep_alive(sock):
    if not sock:
        return
    # start Keep-Alive
    import socket as skt
    sock.setsockopt(skt.SOL_SOCKET, skt.SO_KEEPALIVE, 1)
    # set Keep-Alive interval and retries
    sock.setsockopt(skt.IPPROTO_TCP, skt.TCP_KEEPIDLE, 3)
    sock.setsockopt(skt.IPPROTO_TCP, skt.TCP_KEEPINTVL, 30)
    sock.setsockopt(skt.IPPROTO_TCP, skt.TCP_KEEPCNT, 5)

def  __update_callback(sock):
    """
    try to sync if receive update msg from server
    """
    new_connected = True
    retry_interval = 0
    retry_cnt = 0
    set_keep_alive(sock)
    while True:
        if sock and new_connected:
            send_msg(sock, LONG_CONN, u_token=get_me_info()['token'])
            logger.info("+++ long connection established")
            new_connected = False
        try:
            msg = my_recv(sock, MSG_LEN) if sock else b""
            if not msg: # peer close the conn
                raise Exception
        except: # try to reconnect
            retry_interval = min(2 ** retry_cnt, 3600) # max 3600s per retry
            if retry_cnt < 12:
                retry_cnt += 1
            time.sleep(retry_interval)
            logger.error("long connection closed, try to reconnect ...")
            sock = get_sock(config.server_addr, config.server_port)  # reconnect
            set_keep_alive(sock)
            if sock:
                retry_interval = 1
                retry_cnt = 0
                new_connected = True
            continue
        msg_info = parse_msg(msg.decode())
        msg_type = msg_info['type']
        dir_token = msg_info['d_token']
        if msg_type != UPDATE:
            logger.error("invalid msg type")
            return
        d_info = get_dir_info(token=dir_token)
        # check if dir exist and on managed
        if not (d_info and check_user_dir_exist(get_me_info()['id'], d_info['id'])):
            continue
        dir_path = d_info['path']
        logger.info("recv update msg from server")
        sync_edition(dir_path)


def start_scanner():
    """
    start to watch the managed dirs
    and try to sync, create, commit edition if changed
    """
    # self.scan_timer = timer(self.scan_frequency, 300, self.scan)
    # return self.scan_timer.run(run_imm=True)
    if not self_check():
        logger.error('failed to pass self-check')
        exit(-1)
    ob = Observer()
    __bindcallback(get_sock(config.server_addr, config.server_port), __update_callback)
    for dir_path in config.managed_dirs:
        try:
            sync_init(dir_path)
            create_edition(dir_path)
            commit_edition(dir_path)
            sync_edition(dir_path)
        except Exception:
            logger.error('scan failed: ')
            logger.error(traceback.format_exc())
        handler = MyEventHandler(config.scan_frequency, __scan, dir_path)
        ob.schedule(handler, dir_path, True)
    ob.start()
    logger.info("=================================")
    logger.info("      sync scanner started       ")
    logger.info("=================================")
    ob.join()