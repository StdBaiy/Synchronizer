from os import path as ospath, makedirs
from traceback import format_exc
from .tools import get_sha, logger, parse_msg, replace_sep, gen_token, sync_init
from .db import *
from .conn import *
from .params import config


def register_user(server_sock):
    logger.info("try to register user")
    if not server_sock:
        logger.error("register user failed: can't connect to server")
        return False
    me_info = get_me_info()
    if not me_info:
        logger.error('register user failed: me info doesn\'t exist')
        return False
    name = me_info['name']
    u_token = me_info['token']
    me_id = me_info['id']
    
    send_msg(server_sock, REGISTER_USER, u_token=u_token, addition=name)

    msg = my_recv(server_sock, MSG_LEN)
    msg_info = parse_msg(msg.decode())
    msg_type = msg_info['type']
    user_token = msg_info['addition']
    if msg_type == REGISTER_SUCCESS:
        if not update_user_info(me_id, name, user_token, 1):
        # if not (insert_user(name, user_token) and create_me(name)):
            logger.error("register user failed: something wrong")
            return False
        logger.info("register user ok")
    elif msg_type == REGISTER_FAILED:
        logger.error("register user failed: invalid user name or name already exist")
        return False
    else:
        logger.error("invalid msg type")
        return False
    return True

def modify_user(server_sock, new_name=''):
    # if new_name is None and server_sock is connected,
    # this function will try to change token
    if not server_sock:
        logger.error('modify user failed: can\'t connecte to server')
        return False
    me_info = get_me_info()
    if not me_info:
        logger.error('modify user failed: me info doesn\'t exist')
        return False
    if new_name:
        logger.info("try to modify name from '%s' to '%s'", me_info['name'], new_name)
    else:
        logger.info('try to modify token')
    name = me_info['name']
    user_token = me_info['token']
    registered = me_info['registered']
    me_id = me_info['id']
    if registered == 1 and new_name:
        logger.error('something wrong when rename')
        return False
    
    send_msg(server_sock, MODIFY_USER, u_token=user_token, addition=new_name)

    msg = my_recv(server_sock, MSG_LEN)
    msg_type, _, _, new_token = parse_msg(msg.decode())
    if msg_type == MODIFY_SUCCESS:
        if not update_user_info(me_id, new_name or name, new_token or user_token, 1): # turn to registered
            logger.error("modify user failed: something wrong")
            return False
        logger.info("modify user ok")
    elif msg_type == MODIFY_FAILED:
        logger.error("modify user failed: invalid user name or name already exist")
        return False
    else:
        logger.error("invalid msg type")
        return False
    return True

def register_dirs(server_sock, unreg_dir_paths=[]):
    if not server_sock:
        logger.error('register dirs failed: can\'t connecte to server')
    total_num =  len(unreg_dir_paths)
    if total_num == 0:
        return True
    me_info = get_me_info()
    if not me_info:
        logger.error('modify user failed: me info doesn\'t exist')
        return False
    user_token= me_info['token']
    
    send_msg(server_sock, REGISTER_DIR, u_token=user_token, addition=str(total_num))

    reg_cnt = 0
    for dir_path in unreg_dir_paths:
        dir_path = replace_sep(ospath.abspath(dir_path))
        assert ospath.isdir(dir_path)
        assert check_dir_exist(path=dir_path)
        basename = ospath.basename(dir_path)
        d_info = get_dir_info(path=dir_path)
        d_token = d_info['token']
        reg = d_info['registered']
        # if registered, send token, else set dir token empty
        d_token = "" if reg == 0 else d_token
        
        send_msg(server_sock, REGISTER_DIR, u_token=user_token, d_token=d_token, addition=len(basename))
        server_sock.sendall(basename.encode())
        msg = my_recv(server_sock, MSG_LEN)
        msg_info = parse_msg(msg.decode())
        msg_type = msg_info['type']
        dir_token = msg_info['addition']
        if msg_type == REGISTER_FAILED:
            logger.error("register dir '%s' failed", dir_path)
            continue
        elif msg_type == REGISTER_SUCCESS:
            dir_id = get_dir_info(path=dir_path)['id']
            if not update_dir_info(dir_id, token=dir_token, registered=1):
                logger.error("update local dir failed, something wrong")
            else:
                logger.info("register dir '%s' ok", dir_path)
                reg_cnt += 1
        else:
            logger.error("register dir failed, unknown type")
    return True if reg_cnt == total_num else False

def handle_reg_dir(client_sock, first_msg):
    msg_info = parse_msg(first_msg.decode())
    user_token = msg_info['u_token']
    addition = msg_info['addition']
    u_info = get_user_info(token=user_token, type="server")
    if not u_info:
        return False
    user_name = u_info['name']
    logger.info("recv register dir request from '%s'", user_name)
    total_num = int(addition)
    reg_cnt = 0
    dir_ids = []
    for i in range(total_num):
        msg = my_recv(client_sock, MSG_LEN)
        msg_info = parse_msg(msg.decode())
        u_token = msg_info['u_token']
        d_token = msg_info['d_token']
        len_basename = msg_info['addition']
        basename = my_recv(client_sock, int(len_basename)).decode()
        u_info = get_user_info(token=u_token, type="server")
        if not u_info:
            send_msg(client_sock, REGISTER_FAILED)
            continue
        u_id = u_info['id']
        
        # if dir token is not empty, that means the dir is registered before
        # so try to verify
        if d_token:
            # verify ok
            if check_dir_exist(token=d_token, type="server"):
                d_id = get_dir_info(token=d_token, type="server")['id']
                if not insert_user_dir(u_id, d_id, type="server"):
                    logger.error("associate failed, something wrong")
                    send_msg(client_sock, REGISTER_FAILED)
                else:
                    logger.info("'%s' has registered before, verify ok", basename)
                    send_msg(client_sock, REGISTER_SUCCESS, addition=d_token)
                    dir_ids.append(d_id)
                    reg_cnt += 1
            else:
                # vertify failed
                logger.error("'%s' verify failed")
                send_msg(client_sock, REGISTER_FAILED)
            continue
        
        # dir token is empty, that means the dir is new
        # generate a useable token
        for try_time in range(5):
            new_dir_token = gen_token()
            if not check_dir_exist(token=new_dir_token, type="server"):
                break
        # decide where to store the dir
        for try_time in range(5):
            random_loc = config.storage_location + basename + gen_token(4)
            if not ospath.exists(random_loc):
                makedirs(random_loc, exist_ok=False)
                sync_init(random_loc)
                break
        # try to insert dir into database
        if not insert_dir(new_dir_token, random_loc, registered=1, type="server"):
            logger.error("register dir failed, something wrong")
            send_msg(client_sock, REGISTER_FAILED)
        else:
            # insert ok
            dir_id = get_dir_info(token=new_dir_token, type="server")['id']
            # try to associate if not
            if not insert_user_dir(u_id, dir_id, type="server"):
                logger.error("insert user dir error, something wrong")
                send_msg(client_sock, REGISTER_FAILED)
            else:
                logger.info("register '%s' ok with token '%s'", random_loc, new_dir_token)
                reg_cnt += 1
                dir_ids.append(dir_id)
                send_msg(client_sock, REGISTER_SUCCESS, addition=new_dir_token)
    # clear the associations that not in dir_ids
    clear_associations(u_id, dir_ids, type="server")
    return True if reg_cnt == total_num else False 

def add_exist_dir(local_path, dir_token):
    sock = get_sock(config.server_addr, config.server_port)
    if not sock:
        return False
    me_info = get_me_info()
    assert me_info
    # check from server
    send_msg(sock, ADD_DIR, me_info['token'], dir_token)

    msg = my_recv(sock, MSG_LEN)
    msg_type = parse_msg(msg.decode())['type']
    if msg_type != ADD_DIR_SUCCESS:
        logger.error('something wrong when add dir')
        return False
    if check_dir_exist(path=local_path):
        d_id = get_dir_info(path=local_path)['id']
        if not update_dir_info(d_id, token=dir_token, registered=1):
            logger.error('local add dir failed')
            return False
    elif not insert_dir(dir_token, local_path, registered=1):
        logger.error('local add dir failed')
        return False
    logger.info("add dir '%s' ok", local_path)
    return True

def handle_add_dir(sock, first_msg):
    msg_info = parse_msg(first_msg.decode())
    u_token = msg_info['u_token']
    d_token = msg_info['d_token']
    if not check_user_exist(token=u_token) or not check_dir_exist(token=d_token):
        send_msg(sock, ADD_DIR_FAILED)
        logger.error('add dir failed, user or dir does not exist')
        return False
    u_info = get_user_info(token=u_token)
    u_id = u_info['id']
    d_id = get_dir_info(token=d_token)['id']
    logger.info("'%s' try to add a dir", u_info['name'])
    if check_user_dir_exist(u_id, d_id):
        send_msg(sock, ADD_DIR_SUCCESS)
        logger.info('user-dir already exists')
        return True
    if not insert_user_dir(u_id, d_id):
        logger.error('add failed, something wrong')
        return False
    send_msg(sock, ADD_DIR_SUCCESS)
    logger.info('add dir ok')
    return True

def verify(sock, passwd):
    # try to verify identity
    length ='%04d' % (len(passwd))
    sock.sendall(length) # send length
    sock.sendall(passwd.encode()) # send password
    msg = sock.recv(MSG_LEN)
    if not msg:
        raise Exception # connection err
    msg_info = parse_msg(msg.decode())
    if msg_info['type'] != VERIFY_SUCCESS:
        logger.error('password incorrect')
        return False
    print('password verify ok, try to get cert')
    # get cert
    cert_len = int(my_recv(sock, 4).decode())
    cert_content = my_recv(sock, cert_len)
    with open('cert/server_verify.crt', 'wb') as f:
        f.write(cert_content)
    cert_len = int(my_recv(sock, 4).decode())
    cert_content = my_recv(sock, cert_len)
    with open('cert/client_verify.crt', 'wb') as f:
        f.write(cert_content)
    cert_len = int(my_recv(sock, 4).decode())
    cert_content = my_recv(sock, cert_len)
    with open('cert/client_verify.key', 'wb') as f:
        f.write(cert_content)
    
    return True
        

def handle_verify(sock):
    try:
        passwd_len = int(sock.recv(4).decode())
        passwd = my_recv(sock, passwd_len)
        my_sha = get_sha('cert/passwd', type='sha256')
        recv_sha = get_sha(type='sha256', content=passwd)
        if my_sha != recv_sha:
            send_msg(sock, type=VERIFY_FAILED)
            logger.info('verify password failed')
            sock.close()
            return False
        send_msg(sock, type=VERIFY_SUCCESS)
        # verify ok, transport certs
        # we assert that the server has passed the self-check
        # and the certs are ok
        # send certs in order: server.crt, client.crt, client.key
        with open('cert/server.crt', 'rb') as f:
            content = f.read() # cert is small, read it directly
            cert_len = '%04d' % (len(content))
            sock.sendall(cert_len.encode())
            sock.sendall(content)
        with open('cert/client.crt', 'rb') as f:
            content = f.read() # cert is small, read it directly
            cert_len = '%04d' % (len(content))
            sock.sendall(cert_len.encode())
            sock.sendall(content)
        with open('cert/client.key', 'rb') as f:
            content = f.read() # cert is small, read it directly
            cert_len = '%04d' % (len(content))
            sock.sendall(cert_len.encode())
            sock.sendall(content)
        sock.close()
        return True
    except:
        sock.close()
        logger.error('error when verifying')
        logger.error(format_exc())
        return False
        