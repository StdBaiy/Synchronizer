from time import time, sleep
from os import path as ospath, scandir, remove, rmdir, listdir
import os
import re
import fossil_delta
from shutil import rmtree
from .tools import logger, replace_sep, get_last_ed_nm, parse_edition, parse_msg, check_edition_exist, set_writable
from .db import get_me_info, insert_edition, get_dir_info, check_dir_exist
from .file_processer import *
from .conn import *
from .transfer import transport_edition, recv_edition
from .params import config


def create_edition(dir_path):
    """
    try to create a new edition if
    the workspace changed since last edition
    """
    logger.info("~~~ try to create edition in '%s'", dir_path)

    start_time = time()
    dir_path = replace_sep(ospath.abspath(dir_path)) + '/'
    assert ospath.isdir(dir_path)
    # with open(dir_path + ".sync/editions/changed_flag", "r", encoding="utf-8") as changed_file:
    #     changed = changed_file.read()
    #     if changed == "0":
    #         logger.info("--- changed flag = 0, no change since last edition, creation done")
    #         return False

    new_ed_nm = ("%012d" % start_time) + get_me_info()['name']
    new_ed_dir_path = dir_path + ".sync/editions/" + new_ed_nm[:5]
    new_ed_path = new_ed_dir_path + "/" + new_ed_nm[5:]

    fts, ftl = recursivly_get_fts(dir_path, dir_path)
    extract_time = time()
    logger.debug("extract file tree success, time cost: %dms", (extract_time - start_time) * 1000,)
    if len(fts.splitlines()) == 1:
        logger.info('empty workspace, nothing to create')
        return False
    # if find a pre edition, use delta compression base on it
    last_ed_nm = get_last_ed_nm(dir_path)
    p_res = parse_edition(dir_path, last_ed_nm)
    assert p_res is None or len(p_res) == 3
    if (p_res is None or p_res[0] >= config.quote_num_limit):
        # no last edition or quote num limit exceed, use gzip compress
        ed_stream = b"".join([b"0\n\n", fts])  # queto num = 0
        for _, f_path, sha1 in ftl:
            create_gzip_content(dir_path, f_path, sha1)
    else:  # try delta compression base on last edition if suitable
        l_fts = p_res[2]
        if not check_dir_changed(l_fts, fts):
            logger.info("--- no change since last edition, creation done")
            return False
        ed_stream = f"{int(p_res[0]) + 1}\n{last_ed_nm}\n".encode()
        ed_stream = b"".join([ed_stream, fossil_delta.create_delta(l_fts, fts)])
        for level, f_path, sha1 in ftl:
            l_res = get_last_f_attr(l_fts, level, ospath.basename(f_path))
            if l_res is None:  # new file, use gzip compress
                create_gzip_content(dir_path, f_path, sha1)
            else:
                l_sha1, l_size = l_res
                jud = judge_compress_method(f_path, l_sha1, sha1, l_size)
                if jud == 0:  # delta compress
                    create_delta_content(dir_path, f_path, l_sha1, sha1)
                elif jud == 1:  # gzip compress
                    create_gzip_content(dir_path, f_path, sha1)

    created_time = time()
    logger.info("+++ create content success, time cost: %dms", (created_time - extract_time) * 1000)
    makedirs(new_ed_dir_path, exist_ok=True)
    with open(new_ed_path, "wb") as new_ed_file:
        new_ed_file.write(ed_stream)
    # update last edition
    with open(dir_path + ".sync/editions/last", "w", encoding="utf-8") as last_file:
        last_file.write(new_ed_nm)
    # add to uncommit list for commit
    with open(dir_path + ".sync/editions/uncommit", "a", encoding="utf-8") as uncommit_file:
        uncommit_file.write(new_ed_nm + "\n")
    with open(dir_path + ".sync/editions/changed_flag", "w", encoding="utf-8") as changed_file:
        changed_file.write("0")
    sleep(1)
    return True

def commit_edition(dir_path, edition_name=None):
    """
    read from uncommit file
    and try to commit edition to server
    """
    logger.info("~~~ try to commit edition")
    dir_path = replace_sep(ospath.abspath(dir_path)) + '/'
    assert ospath.isdir(dir_path) and check_dir_exist(path=dir_path)
    if not edition_name:
        with open(dir_path + ".sync/editions/uncommit", "r", encoding="utf-8") as uncommit_file:
            ed_list = [x.strip() for x in uncommit_file.readlines()]
    else:
        ed_list = [edition_name]
    if len(ed_list) == 0:
        logger.info("no edition to commit\n")
        return True
    new_ed_list = ed_list.copy()
    sock = tcp_ssl_connect(config.server_addr, config.server_port)
    if not sock:
        logger.error("connection failed\n")
        return False
    user_token = get_me_info()['token']
    dir_token = get_dir_info(path=dir_path)['token']
    send_msg(sock, UPLOAD_REQUEST, u_token=user_token, d_token=dir_token, addition=str(len(ed_list)))
    commit_cnt = 0
    for ed_name in ed_list:
        if transport_edition(sock, dir_path, ed_name):
            logger.info(">>> commit edition '%s' success\n", ed_name)
            new_ed_list.remove(ed_name)
            commit_cnt += 1
        else:
            logger.error("!!! commit edition '%s' failed\n", ed_name)
        msg = my_recv(sock, MSG_LEN)
        timestamp = parse_msg(msg.decode())['addition']
        d_id = get_dir_info(path=dir_path)['id']
        insert_succ = insert_edition(d_id, ed_name, timestamp=timestamp.strip())
    sock.close()
    if not edition_name:
        with open(dir_path + ".sync/editions/uncommit", "w", encoding="utf-8") as f2:
            f2.writelines([x + "\n" for x in new_ed_list])
    return commit_cnt == len(ed_list)

def sync_edition(dir_path, edition_name=None):
    """
    read from last_sync file
    and sync all editions after last_sync
    """
    logger.info("~~~ try to sync edition")
    dir_path = replace_sep(ospath.abspath(dir_path)) + '/'
    assert ospath.isdir(dir_path)

    user_token = get_me_info()['token']
    dir_info = get_dir_info(path=dir_path)
    assert dir_info
    dir_token = dir_info['token']
    with open(dir_path + ".sync/editions/last_sync", "r", encoding="utf-8") as last_sync_file:
        last_sync_ed = last_sync_file.read().strip()
    sock = tcp_ssl_connect(config.server_addr, config.server_port)
    if not sock:
        logger.error("sync failed")
        return
    send_msg(sock, DOWNLOAD_REQUEST, u_token=user_token, d_token=dir_token, addition=last_sync_ed)
    # res = recv_msg(sock)
    first_msg = my_recv(sock, MSG_LEN)
    msg_info = parse_msg(first_msg.decode())
    msg_type = msg_info['type']
    dir_token = msg_info['d_token']
    ed_num = msg_info['addition']
    if msg_type != SYNC_REQUEST:
        return False
    dir_path = replace_sep(get_dir_info(dir_token)['path'])
    if not dir_path.endswith("/"):
        dir_path += "/"
    succ_cnt = 0
    for sync_num in range(int(ed_num)):
        ed_name = recv_edition(dir_path, sock)
        if not ed_name:
            break
        msg = my_recv(sock, MSG_LEN)
        msg_type, _, _, timestamp = parse_msg(msg.decode())
        d_id = get_dir_info(path=dir_path)['id']
        insert_succ = insert_edition(d_id, ed_name, timestamp=timestamp.strip())
        if insert_succ:
            succ_cnt += 1
            logger.info("sync edition '%s' success", ed_name)
        with open(dir_path + ".sync/editions/last_sync", "w", encoding="utf-8") as last_sync_file:
            last_sync_file.write(ed_name)
    sock.close()
    if succ_cnt == 0:
        logger.info("current workspace is already the latest, no edition to sync")
        return True
    else:
        logger.info("<<< sync %d edition(s) finished", succ_cnt)
        if config.always_cover:
            with open(dir_path + ".sync/editions/last_sync", "r", encoding="utf-8") as last_sync_file:
                last_sync_ed = last_sync_file.read().strip()
            revert_edition(dir_path, last_sync_ed)
        return True
    
def _recursivly_remove(dir_path, ignore_rules, root_path=None):
    # return true if all contents are removed, else return false
    assert(ospath.isdir(dir_path))
    if not root_path:
        root_path = dir_path
    all_removed = True
    for item_path in listdir(ospath.abspath(dir_path)):
        full_path = dir_path + item_path
        if ospath.isdir(full_path) and full_path.endswith(".sync"):
            continue
        if ospath.islink(full_path): # do not remove symlink
            continue
        # check ignore
        rel_path = full_path.replace(root_path, '')
        if ospath.isdir(full_path):
            rel_path += '/'
        ignore = False
        for rule in ignore_rules:
            if re.match(rule, rel_path):
                ignore = True
                all_removed = False
                break
        if ignore:
            continue

        if ospath.isfile(full_path):
            set_writable(full_path)
            remove(full_path)
        elif ospath.isdir(full_path):
            # if files are totally removed, then remove the dir
            if _recursivly_remove(full_path + '/', ignore_rules, root_path=root_path):
                set_writable(full_path)
                rmdir(full_path) # remove the empty dir
            else:
                all_removed = False
    return all_removed

def revert_edition(dir_path, edition_name):
    """
    try to revert to specified edition
    if the edition is last edition and workspace do not change
    since last edition, then just return
    """
    # print(datetime.now(), "start revert")
    if not check_edition_exist(dir_path, edition_name):
        return False
    logger.info("*** revert edition '%s'", edition_name)
    start_time = time()
    dir_path = replace_sep(ospath.abspath(dir_path)) + '/'
    assert ospath.isdir(dir_path)
    last_ed_nm = get_last_ed_nm(dir_path) or ""
    if (last_ed_nm == edition_name):  # check if the dir has changed since last edition
        # with open(
        #     dir_path + ".sync/editions/changed_flag", "r", encoding="utf-8"
        # ) as changed_file:
        #     changed = changed_file.read()
        # if changed == "0":
        #     logger.info(
        #         "--- changed flag = 0, no change since last edition, revert done"
        #     )
        #     return False
        p_res = parse_edition(dir_path, last_ed_nm)
        fts, _ = recursivly_get_fts(dir_path, dir_path)
        assert p_res and len(p_res) == 3
        if not check_dir_changed(p_res[2], fts):
            logger.info("--- no change since last edition, revert done")
            return False
  
    # clear current workspace
    ignore_rules = []
    with open(dir_path + '.sync/ignore', 'r') as ignore_file:
        for rule in ignore_file.readlines():
            rule = rule.strip()
            if rule.startswith("#"):
                continue
            ignore_rules.append(rule)
    _recursivly_remove(dir_path, ignore_rules)

    clear_time = time()
    logger.info("remove current workspace, time cost: %dms", (clear_time - start_time) * 1000)
    # get edition
    p_res = parse_edition(dir_path, edition_name)
    assert p_res and len(p_res) == 3
    _, _, fts = p_res
    ftl = fts.splitlines()
    recursivly_create(dir_path, ftl, ignore_rules=ignore_rules)
    recovery_time = time()
    # change last edition
    with open(dir_path + ".sync/editions/last", "w", encoding="utf-8") as last_file:
        last_file.write(edition_name)
    with open(dir_path + ".sync/editions/changed_flag", "w", encoding="utf-8") as changed_file:
        changed_file.write("0")
    logger.info("create new workspace, time cost: %dms", (recovery_time - clear_time) * 1000)
    # print(datetime.now(), 'revert done')
    return True