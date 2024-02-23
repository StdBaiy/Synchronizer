from time import time
from os import path as ospath, makedirs
from shutil import move, copy
from .conn import *
from .tools import replace_sep, parse_msg, parse_edition, check_edition_exist, check_content_exist, logger
from .file_processer import parse_fts_line
from .db import *
from .params import global_var

def transport_edition(sock, dir_path, edition_name, type="client"):
    logger.debug("start to transport edition '%s'", edition_name)
    dir_path = replace_sep(dir_path)
    if not dir_path.endswith("/"):
        dir_path += "/"
    assert ospath.exists(dir_path)

    ed_path = (dir_path + ".sync/editions/" + edition_name[:5] + "/" + edition_name[5:])
    assert ospath.exists(ed_path)
    with open(ed_path, "rb") as ed_file:
        ed_stream = ed_file.read()
    user_token = get_me_info(type=type)['token']
    dir_token = get_dir_info(path=dir_path, type=type)['token']
    send_msg(sock, UPLOAD_REQUEST, user_token, dir_token, edition_name + "|" + str(len(ed_stream)))
    # send edition
    sock.sendall(ed_stream)
    logger.debug("send edition '%s'", edition_name)
    msg = my_recv(sock, MSG_LEN)
    if not msg:
        return False
    msg_info = parse_msg(msg.decode())
    msg_type = msg_info['type']
    need_len = msg_info['addition']
    if msg_type == REFUSE:
        logger.debug("peer refused the transmission of edition '%s' because already committed", edition_name)
        return True
    need = my_recv(sock, int(need_len))
    logger.debug("recv need msg")
    logger.debug("need to send %d files", need.count(b"1"))
    p_res = parse_edition(dir_path, edition_name, ed_content=ed_stream)
    if p_res:
        _, _, fts = p_res
        logger.debug("parse edition '%s' ok", edition_name)
    else:
        logger.error("parse edition '%s' failed", edition_name)
        return False
    ftl = fts.splitlines()
    assert len(need) == len(ftl)  # they are corresponding
    # start to send files
    idx = 0
    for item in ftl:
        if need[idx] == 49:  # 49 is ascii code of '1'
            # transport file
            _, _, _, sha1, _, _, _, _ = parse_fts_line(item)
            c_path = dir_path + ".sync/contents/" + sha1[:2] + "/" + sha1[2:]
            with open(c_path, "rb") as content_file:
                content = content_file.read()          
            send_msg(sock, SEND_FILE_BLOCK, addition=str(len(content)) + '|' + sha1)
            sock.sendall(content)
            logger.debug("send file '%s', size %d Bytes", sha1, len(content))
        idx += 1
    logger.debug("send all files")
    msg = my_recv(sock, MSG_LEN)  # receive finish msg
    msg_type = parse_msg(msg.decode())['type']
    if msg_type == UPLOAD_SUCCESS:
        logger.info("send edition '%s' ok", edition_name)
    else:
        logger.error("send edition '%s' failed", edition_name)
    return msg_type == UPLOAD_SUCCESS

def recv_edition(dir_path, sock):
    """
    receive edition from another node
    and save it into .sync dir
    """
    msg = my_recv(sock, MSG_LEN)
    if not msg:
        return None

    addition = parse_msg(msg.decode())['addition']
    start_time = time()
    ed_name, ed_size = addition.split("|")
    ed_stream = my_recv(sock, int(ed_size))

    if check_edition_exist(dir_path, ed_name):
        logger.info("edition '%s' already exist", ed_name)
        send_msg(sock, REFUSE)
        return ed_name
    # save into tmp dir
    with open("tmp/" + ed_name, "wb") as ed_f:
        ed_f.write(ed_stream)
    logger.debug("recv edition '%s', size %d Bytes, cost time %.2fms", ed_name, len(ed_stream), (time() - start_time) * 1000)
    ed_time = time()
    # must parse first, or the fts maybe delta code
    # that means the earlier edition must exist
    p_res = parse_edition(dir_path, ed_name, ed_content=ed_stream)
    if p_res:
        _, _, fts = p_res
    else:
        logger.error("parse edition '%s' failed", ed_name)
        return None
    logger.debug("parse edition '%s', cost time %.2fms", ed_name, (time() - ed_time) * 1000)
    ftl = fts.splitlines()
    need = b""  # the files that need to be uploaded
    idx = 0
    for item in ftl:
        _, flag, _, sha1, _, _, _, _ = parse_fts_line(item)
        if flag == 1 and not check_content_exist(dir_path, sha1):
            need = need + b"1"
        else:
            need = need + b"0"
        idx = idx + 1
    logger.debug("need to recv %d files", need.count(b"1"))
    msg = (MSG_FORMAT % (ALLOW_UPLOAD, 0, 0, str(len(need)))).encode()
    sock.send(msg)
    sock.send(need)
    logger.debug("send need msg")
    # recv the files that need to be uploaded
    need_time = time()
    for i in range(need.count(b"1")):
        content_time = time()
        msg = my_recv(sock, MSG_LEN)
        addition = parse_msg(msg.decode())['addition']
        file_size, sha1 = addition.split("|")
        file_content = my_recv(sock, int(file_size))
        # save into tmp dir
        with open("tmp/" + sha1, "wb") as tmp_content_file:
            tmp_content_file.write(file_content)
        logger.debug("recv file '%s', size %d Bytes, cost time %.2fms", sha1, len(file_content), (time() - content_time) * 1000)
    logger.debug("recv all files, cost time %.2fms", (time() - need_time) * 1000)
    recv_time = time()
    # save contents
    idx = -1
    for item in ftl:
        idx = idx + 1
        if need[idx] == 48:
            continue  # '0' == 48
        _, _, _, sha1, _, _, _, _ = parse_fts_line(item)
        c_dir = dir_path + ".sync/contents/" + sha1[:2]
        c_path = c_dir + "/" + sha1[2:]
        makedirs(c_dir, exist_ok=True)
        copy("tmp/" + sha1, c_path)
    # save edition
    logger.debug("move edition '%s', cost time %.2fms", ed_name, (time() - recv_time) * 1000)
    ed_dir_path = dir_path + ".sync/editions/" + ed_name[:5]
    ed_path = ed_dir_path + "/" + ed_name[5:]
    makedirs(ed_dir_path, exist_ok=True)
    copy("tmp/" + ed_name, ed_path)

    # send succ msg
    msg = (MSG_FORMAT % (UPLOAD_SUCCESS, 0, 0, 0)).encode()
    sock.send(msg)
    logger.info("recv edition '%s' ok", (ed_name))
    return ed_name

def handle_upload(first_msg, client_sock):
    msg_info = parse_msg(first_msg.decode())
    user_token = msg_info['u_token']
    dir_token = msg_info['d_token']
    ed_num = msg_info['addition']
    user_name = get_user_info(token=user_token, type="server")['name']
    dir_path = replace_sep(get_dir_info(dir_token, type="server")['path'])
    if not dir_path.endswith("/"):
        dir_path += "/"
    
    logger.info("~~~ receive upload request from '%s'", user_name)
    cnt = 0
    ed_num = int(ed_num)
    for recv_num in range(ed_num):
        ed_name = recv_edition(dir_path, client_sock)
        if not ed_name:
            break
        # only fist time will success
        d_id = get_dir_info(path=dir_path)['id']
        inser_succ = insert_edition(d_id, ed_name, type="server")
        send_msg(client_sock, TIME_STAMP, addition=get_commit_time(ed_name, type="server"))
        cnt += 1
    logger.info("<<< upload %d edition(s) finished\n", cnt)
    notify_update(dir_token, exclude=[user_token])
    return True, dir_path, ed_name

def handle_sync(server_sock):
    first_msg = my_recv(server_sock, MSG_LEN)
    msg_type, _, dir_token, ed_num  = parse_msg(first_msg.decode())
    if msg_type != SYNC_REQUEST:
        return False
    dir_path = replace_sep(get_dir_info(dir_token)['path'])
    if not dir_path.endswith("/"):
        dir_path += "/"
    succ_cnt = 0
    for sync_num in range(int(ed_num)):
        ed_name = recv_edition(dir_path, server_sock)
        if not ed_name:
            break
        msg = my_recv(server_sock, MSG_LEN)
        msg_info = parse_msg(msg.decode())
        msg_type= msg_info['type']
        timestamp = msg_info['addition']
        d_id = get_dir_info(path=dir_path)['id']
        insert_succ = insert_edition(d_id, ed_name, timestamp=timestamp.strip())
        if insert_succ:
            succ_cnt += 1
            logger.info("sync edition '%s' success", ed_name)
        with open(dir_path + ".sync/editions/last_sync", "w", encoding="utf-8") as last_sync_file:
            last_sync_file.write(ed_name)
    server_sock.close()
    if succ_cnt == 0:
        logger.info("current workspace is already the latest, no edition to sync")
        return True
    else:
        logger.info("<<< sync %d edition(s) finished", succ_cnt)
        return True
    
def handle_download(first_msg, client_sock):
    msg_info = parse_msg(first_msg.decode())
    user_token = msg_info['u_token']
    dir_token = msg_info['d_token']
    last_sync_ed_name = msg_info['addition']
    user_name = get_user_info(token=user_token, type="server")['name']
    d_info = get_dir_info(dir_token, type="server")
    dir_path = replace_sep(d_info['path'])
    logger.info("recv download request from '%s'", user_name)
    if not last_sync_ed_name:
        # choose a time that must be earlier than all editions
        sync_time = "1970-01-01 00:00:00.000"
    else:
        sync_time = get_commit_time(last_sync_ed_name, type="server")
    
    ed_list = [x[0] for x in filter_ed_by_time(d_info['id'], sync_time, type="server")]
    ed_list.sort()
    if len(ed_list) == 0:
        logger.info("'%s' is already the latest, no edition to sync", user_name)

    send_msg(client_sock, SYNC_REQUEST, get_me_info(type="server")['token'], dir_token, str(len(ed_list)))

    for ed_name in ed_list:
        logger.info("try to send edition '%s'", ed_name)
        if not transport_edition(client_sock, dir_path, ed_name, type="server"):
            logger.error("send edition '%s' failed", ed_name)
        else:
            logger.info("send edition '%s' ok", ed_name)
        send_msg(client_sock, TIME_STAMP, addition=get_commit_time(ed_name, type="server"))
    logger.info(">>> '%s' download %d edition(s) finished", user_name, len(ed_list))
    return True

def notify_update(dir_token, exclude=[]):
    """
    notify the client to sync new edition
    """
    my_token = get_me_info()['token']
    token_list = list(global_var.conn_pool.keys())
    for u_token in token_list:
        if u_token in exclude:
            continue
        try:
            logger.info("notify update to '%s'", get_user_info(token=u_token)['name'])
            send_msg(global_var.conn_pool[u_token], UPDATE, my_token,dir_token)
        except Exception as err:
            logger.error("notify update failed: %s", str(err))
            global_var.conn_pool[u_token].close()
            del global_var.conn_pool[u_token]
            continue