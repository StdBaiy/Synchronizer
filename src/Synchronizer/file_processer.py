# from Synchronizer import sync
from .tools import logger, check_ignore, replace_sep, get_sha, change_attr, check_content_exist
from .params import config
import fossil_delta
from os import path as ospath, makedirs, scandir, stat as osstat
import gzip
import re

def create_delta_content(dir_path, f_path, l_sha1, sha1, quote_limit=10):
    l_c_path = dir_path + ".sync/contents/" + l_sha1[:2] + "/" + l_sha1[2:]
    with open(l_c_path, "rb") as quote_content_file:
        q_num = int(quote_content_file.readline().strip())
    if q_num >= quote_limit:  # arrive quote limit, create gzip content
        create_gzip_content(dir_path, f_path, sha1)
        return
    l_data = __decompress(dir_path, l_sha1)
    content_dir_path = dir_path + ".sync/contents/" + sha1[:2]
    makedirs(content_dir_path, exist_ok=True)
    content_path = content_dir_path + "/" + sha1[2:]
    with open(f_path, "rb") as origin_content_file:
        delta = fossil_delta.create_delta(l_data, origin_content_file.read())
    with open(content_path, "wb") as content_file:  # write compress method
        content_file.write(f"{q_num + 1}\n".encode())
        content_file.write(l_sha1.encode() + b"\n")
        content_file.write(delta)

def create_gzip_content(dir_path, f_path, sha1):
    if check_content_exist(dir_path, sha1):
        return
    content_dir = dir_path + ".sync/contents/" + sha1[:2]
    makedirs(content_dir, exist_ok=True)
    content_path = content_dir + "/" + sha1[2:]
    with open(content_path, "wb") as content_file:  # write compress method
        content_file.write(b"0\n\n")
        with open (f_path, "rb") as c_file:
            content_file.write(gzip.compress(c_file.read()))
    return ospath.getsize(content_path)

def __decompress(dir_path, sha1, block_size=64 * 1024 * 1024):
    # decompress content_path
    content_path = dir_path + ".sync/contents/" + sha1[:2] + "/" + sha1[2:]
    with open(content_path, "rb") as content_file:
        q_num = content_file.readline().strip()
        q_sha1 = content_file.readline().strip()
        content = content_file.read()
        if q_num == b"0":  # gzip compress
            return gzip.decompress(content)
        else:  # delta compress
            q_data = __decompress(dir_path, q_sha1.decode())
            return fossil_delta.apply_delta(q_data, content)

def __revert_content(dir_path, f_path, sha1, size):
    if not check_content_exist(dir_path, sha1):
        raise Exception("content not exist, should ask server")
    f_content = __decompress(dir_path, sha1, f_path) if sha1 != "" else b""
    with open(f_path, "wb") as content_file:
        content_file.write(f_content)
        # content_file.flush()
        # os.fsync(content_file.fileno())
    logger.debug("create file '%s' done, size %d", f_path, ospath.getsize(f_path))
    # if size != 0: raise Exception('revert content size error')

def judge_compress_method(f_path, l_sha1, sha1, l_size):
    # judge compress method by file size, 0 for delat compress, 1 for gzip compress
    f_size = ospath.getsize(f_path)
    if f_size == 0 or l_size == 0:
        return 1  # one of file is empty, use gzip
    if f_size > 64 * 1024 * 1024:
        return 1  # file is too large, use gzip
    sz_ratio = min(l_size, f_size) / max(l_size, f_size)
    if sz_ratio < 0.5:
        return 1  # size difference is too large, use gzip

    # try to use delta compress and check effect
    return 0

def parse_fts_line(line):
    (
        level,
        flag,
        f_size,
        sha1,
        c_time,
        m_time,
        permission,
        name,
    ) = line.decode().split("|", 7)
    return (
        int(level),
        int(flag),
        int(f_size) if f_size != "" else None,
        sha1,
        int(c_time),
        int(m_time),
        int(permission),
        name,
    )

def get_last_f_attr(l_fts, level, f_name):
    # get same file sha1 vlue in last edition file tree, this is for delta compresssion
    ftl = l_fts.splitlines()
    for line in ftl:
        lev, _, size, sha1, _, _, _, name = parse_fts_line(line)
        if lev == level and name == f_name:
            return sha1, size
    return None

def check_dir_changed(l_fts, fts):
    # check if file tree is changed
    # ignore the c_time, m_time and perimission change
    l_ftl = l_fts.splitlines()
    ftl = fts.splitlines()
    if len(l_ftl) != len(ftl):
        return True
    for i in range(len(l_ftl)):
        l_level, l_flag, _, l_sha1, _, _, _, l_name = parse_fts_line(l_ftl[i])
        level, flag, _, sha1, _, _, _, name = parse_fts_line(ftl[i])
        if l_level != level or l_flag != flag or l_sha1 != sha1 or l_name != name:
            return True
    return False

def recursivly_get_fts(dir_path, now_path, intent=0, ignore_list=None):
    # return file tree stream, file tree list
    assert dir_path and now_path
    assert ospath.exists(now_path) and ospath.isdir(now_path)
    if ignore_list is None:  # get ignore list
        ignore_list = []
        with open(dir_path + ".sync/ignore", "r", encoding="utf-8") as ignore_file:
            for rule in ignore_file.readlines():
                rule = rule.strip()
                if rule.startswith("#"):
                    continue
                ignore_list.append(rule)
    dir_stat = osstat(now_path)
    ospath.realpath(now_path)
    fts = (
        rf"{intent}|0|||{int(dir_stat.st_ctime)}|{int(dir_stat.st_mtime)}|{dir_stat.st_mode}|{ospath.basename(ospath.realpath(now_path))}"
        + "\n"
    ).encode()
    ftl = []
    intent = intent + 1
    for entry in scandir(now_path):
        rel_path = replace_sep(entry.path.replace(dir_path, ''))
        if entry.is_dir():
            rel_path += '/'
        if check_ignore(rel_path, ignore_list, file_size_limit=config.file_size_limit):
            continue
        stat = entry.stat()
        if entry.is_file():
            sha1 = get_sha(replace_sep(entry.path))
            fts = b"".join(
                [
                    fts,
                    (
                        rf"{intent}|1|{stat.st_size}|{sha1}|{int(stat.st_ctime)}|{int(stat.st_mtime)}|{stat.st_mode}|{entry.name}"
                        + "\n"
                    ).encode(),
                ]
            )
            if not check_content_exist(dir_path, sha1):
                ftl.append((intent, rf"{replace_sep(entry.path)}", sha1))
        elif entry.is_dir():
            ignore_file, l = recursivly_get_fts(
                dir_path, replace_sep(entry.path), intent, ignore_list
            )
            fts = b"".join([fts, ignore_file])
            ftl.extend(l)
    return fts, ftl  # bytes, ls(turple)

def recursivly_create(dir_path, ftl, now_path=None, index=0, ignore_rules=[]):
    if now_path is None:
        now_path = dir_path
    now_path = replace_sep(ospath.abspath(now_path)) + '/'
    (
        father_level,
        _,
        _,
        _,
        father_c_time,
        father_m_time,
        father_permission,
        name,
    ) = parse_fts_line(ftl[index])
    if not check_ignore(now_path.replace(dir_path, ''), ignore_rules):
        makedirs(now_path, exist_ok=True)
    logger.debug("create dir '%s' done", now_path)
    i = index
    while i + 1 < len(ftl):
        i = i + 1
        (
            level,
            flag,
            f_size,
            sha1,
            c_time,
            m_time,
            permission,
            name,
        ) = parse_fts_line(ftl[i])
        if level < father_level:
            return i - 1
        if level > father_level + 1:
            continue
        level_path = (
            now_path
            if level > father_level
            else replace_sep(ospath.dirname(now_path[:-1])) + '/' # parent dir of now_path
        )
        if flag == 0:  # is dir
            i = recursivly_create(dir_path, ftl, level_path + name, i, ignore_rules=ignore_rules)
        elif flag == 1:  # is file
            # check ignore
            rel_path = (level_path + name).replace(dir_path, '')
            if check_ignore(rel_path, ignore_rules):
                continue
            __revert_content(dir_path, level_path + name, sha1, f_size)
            change_attr(level_path + name, c_time, m_time, permission)
        else:
            raise Exception("invalid file type")
    change_attr(now_path, father_c_time, father_m_time, father_permission)
    return len(ftl)