from operator import truediv
from os import path as ospath
from time import time
from .db import *
from .tools import gen_cert, logger, gen_random_name, gen_token
from .msg import register_user, modify_user, register_dirs
from .conn import *
from .params import config, global_var

def self_check():
    # must run with order
    t1 = time()
    print('synchronizer is self-checking...')
    if not __check_cert():
        print("failed to pass cert check")
        return False
    print("passed cert check")
    if not __check_database():
        print("failed to pass database check")
        return False
    print("passed database check")
    if not __check_me():
        print("failed to pass user check")
        return False
    print("passed user check")
    if not __check_dirs():
        print("failed to pass dir check")
        return False
    print("passed dir check")
    print('self-check ok, cost %.2fms' % ((time() - t1) * 1000))
    return True

def __check_cert():
    if global_var.node == "server":
        if not ospath.isfile('cert/server.crt') \
        or not ospath.isfile('cert/server.key') \
        or not ospath.isfile('cert/client.crt') \
        or not ospath.isfile('cert/client.key'):
            gen_cert('server')
            gen_cert('client')
        if not ospath.isfile('cert/passwd'):
            # server must create a passwd before running
            return False
    if global_var.node == "client":
        if not ospath.isfile('cert/server_verify.crt') \
        or not ospath.isfile('cert/client_verify.crt') \
        or not ospath.isfile('cert/client_verify.key'):
            # client must have cert to run
            return False
    return True


def __check_database():
    create_tables()
    return True

def __check_me():
    me_info = get_me_info()
    if not me_info:
        logger.debug('no info, try to create me')
        # user didn't give a name, generate a random one
        token = gen_token()
        name = config.device_name if config.device_name else gen_random_name()
        succ = insert_user(name, token, registered=0) and create_me(name)
        if succ:
            logger.debug('create me ok')
            config.device_name = name # write into config, TODO
        else:
            logger.debug("create me failed: name: '%s', token: '%s'", name, token)

        # if create me succ, this shall go to 'else' statment to check whether registered
        # if failed, most likely due to duplicate name, it will re-generate one
        return __check_me()
    else: # local me exists, check whether registered
        db_name = me_info['name']
        db_token = me_info['token']
        registered = me_info['registered']
        db_id = me_info['id']
        # check if user name are same with config
        if config.device_name and (db_name != config.device_name):
            # try to modify the name
            logger.info('try to rename')
            # check validation of params.device_name, TODO
            if not update_user_info(db_id, config.device_name, db_token , 0): # turn to unregistered
                logger.error("modify user failed: invalid or duplicate name")
                return False
            logger.info('rename local user ok')
            if global_var.node == 'server':
                logger.info('check me ok')
                return True
            sock = get_sock(config.server_addr, config.server_port)
            if sock:
                if modify_user(sock, config.device_name):
                    logger.info('check me done, existed and registered')
                    return True
                else:
                    logger.error('register modify failed: invalid or duplicate name')
                    return False
            logger.info('check me done, existed but not registered')
            return True
        if global_var.node == 'server':
            logger.info('check me ok')
            return True
        if registered == 1:
            # pass the check
            logger.info('check me done, existed and registered')
            return True
        else: # try to register, server will gen a new token
            logger.info('me info existed but not registered, try to register')
            # try to use local me info to register
            sock = get_sock(config.server_addr, config.server_port)
            if sock: # sock is only for test connection
                if register_user(sock):
                    sock.close()
                    logger.info('register me ok, existed and registered')
                    return True
                else:
                    sock.close()
                    logger.error('register me failed: invalid or duplicate name')
                    return False
            logger.info('check me done, not registered')
            return True

def __check_dirs(): 
    if not config.managed_dirs:
        logger.info('check dirs ok, no dir on managed')
        return True
    dir_tokens = []
    dir_paths = []
    dir_ids = []
    unreg_num = 0
    me_id = get_me_info()['id']
    # clear all association before
    for dir_path in config.managed_dirs:
        if not ospath.isdir(dir_path):
            logger.error("'%s' is not a dir", dir_path)
            continue
        if not check_dir_exist(path=dir_path):
            logger.info("dir '%s' is not in datebase or moved, try to create a new one", dir_path)
            for try_time in range(5): # make sure create is successful
                token = gen_token()
                if insert_dir(token, dir_path, registered=0):
                    logger.info('created ok')
                    break
        d_info = get_dir_info(path=dir_path)
        dir_token = d_info['token']
        dir_id = d_info['id']
        registered = d_info['registered']
        dir_tokens.append(dir_token)
        dir_ids.append(dir_id)
        if not registered:
            dir_paths.append(dir_path)
            unreg_num += 1
        # associate with me if not
        if not check_user_dir_exist(me_id, dir_id):
            insert_user_dir(me_id, dir_id)
    # clear the associations that not in dir_ids
    clear_associations(me_id, dir_ids)
    if global_var.node == 'server':
        logger.info('check dirs ok')
        return True
    if unreg_num > 0:
        sock = get_sock(config.server_addr, config.server_port)
        if sock:
            logger.info('try to register dir')
            if register_dirs(sock, dir_paths):
                logger.info('register dirs ok')
                logger.info('check dirs ok')
                return True
        else:
            logger.error('register dir failed')
            logger.info('check dirs done, some not registered')
            return False
    logger.info('check dirs ok')
    return True