'''
this module is for control synchronizer manually
'''

from ast import parse
from os import path as ospath, system as sys_exec, scandir
from platform import system as platform_sys
from turtle import clearscreen
from Synchronizer.params import config
from Synchronizer.edition import create_edition, commit_edition, revert_edition
from Synchronizer.db import *
from Synchronizer.tools import get_sha, replace_sep, logger, gen_token, parse_msg
from Synchronizer.conn import *
from Synchronizer.msg import verify
import time
import sys

SCANNER_NAME = 'sync_scanner'
SERVER_NAME = 'sync_server'

if platform_sys() == "Windows":
    from win_task import *

# def get_user_input(timeout=10):
#     user_input = []

#     def input_thread():
#         try:
#             user_input.append(input())
#         except Exception:
#             pass

#     input_thread = threading.Thread(target=input_thread)
#     input_thread.daemon = True
#     input_thread.start()
#     if timeout <= 0:
#         input_thread.join()
#     else:
#         input_thread.join(timeout)

#     if user_input:
#         return user_input[0]
#     else:
#         return None
    
def manage_edition(now_dir):
    while True:
        clear_screen()
        print("\n\n================= synchronizer console =================")
        d_info = get_dir_info(path=now_dir)
        print("  path: '%s'" % d_info['path'])
        print("  token: '%s'" % d_info['token'])
        print("  registered: '%s'" % d_info['registered'])
        print('  [edition] 1: show editions; 2: create edition; 3: commit editions; e: exit')
        option = input()
        if option == '1':
            show_editions(now_dir)
        elif option == '2':
            create_edition(now_dir)
        elif option == '3':
            commit_edition(now_dir)
        elif option == 'e':
            break
        else:
            input('invalid input')
            continue

def manage_dir():
    while True:
        clear_screen()
        print("\n\n================= synchronizer console =================")
        print('  [dir] dir-index: manage edition; a: add a dir; e: exit')
        idx = 0
        if len(config.managed_dirs) == 0:
            print("no dir now, add dir in config or input 'a' to add an exsit dir")
        else:
            for dir in config.managed_dirs:
                idx = idx + 1
                print('*', idx, dir)
        ipt = input()
        try:
            if ipt == 'e': break
            elif ipt == 'a':
                add_a_dir()
                continue
            ipt = int(ipt)
            if ipt > len(config.managed_dirs) or ipt <= 0:
                raise Exception
        except Exception:
            input('invalid input, press any key to continue')
            continue
        now_dir = config.managed_dirs[ipt - 1]
        manage_edition(now_dir)

def __scan_ed(ed_path, num=10):
    ed_path = replace_sep(ed_path)
    cnt = num
    ed_list = []
    assert ospath.exists(ed_path) and ospath.isdir(ed_path)
    for entry in sorted(scandir(ed_path), key=lambda x: x.name, reverse=True):
        if not entry.is_dir():
            continue
        for ed in sorted(scandir(entry.path), key=lambda x: x.name, reverse=True):
            if not ed.is_file():
                continue
            ed_list.append(entry.name + ed.name)
            cnt = cnt - 1
            if cnt == 0:
                cnt = num
                yield ed_list
                ed_list.clear()
    yield ed_list

def show_editions(dir_path, num=10):
    """
    try to show latest num editions
    and user can select one to revert
    """
    # read latest-num editions
    assert ospath.exists(dir_path)
    dir_path = replace_sep(dir_path)
    if not dir_path.endswith("/"):
        dir_path = dir_path + "/"
    ed_dir = dir_path + ".sync/editions/"
    ed_gen = __scan_ed(ed_dir, num)
    ed_list = None
    try:
        ed_list = next(ed_gen).copy()
    except StopIteration:
        pass
    assert ed_list is not None
    if len(ed_list) == 0:
        print("no editions")
        return
    print("latest", len(ed_list), "editions:")
    idx = 0
    for ed_name in ed_list:
        date = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(int(ed_name[:12])))
        token = ed_name[12:]
        print(idx, date, "created by", token)
        idx = idx + 1
    while True:
        print("  [edition] index: revert edition; m: show more editions; e: exit")
        cmd = input()
        if cmd == "e":
            return
        if cmd == "m":
            try:
                tmp_list = next(ed_gen)
            except StopIteration as err:
                tmp_list = err.value
            if not tmp_list or len(tmp_list) == 0:
                print("no more editions")
                continue
            ed_list.extend(tmp_list)
            for ed_name in tmp_list:
                date = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(int(ed_name[:12])))
                token = ed_name[12:]
                print(idx, date, "created by", token)
                idx = idx + 1
            continue
        try:
            select_idx = int(cmd)
            if select_idx < 0 or select_idx >= len(ed_list):
                raise Exception("invalid index")
        except Exception:
            input('invalid input, press any key to continue')
            continue
        revert_edition(dir_path, ed_list[select_idx])

# def check_service_status():
#     service = None
#     try:
#         import psutil
#         service = psutil.win_service_get(params.service_name)
#         service = service.as_dict()
#     except Exception:
#         pass
#     print(params.service_name, " is ", service["status"] if service else "not installed")


# def manage_service():
#     win_cmd_head = ''
#     proj_dir = ospath.abspath(params.proj_dir)
#     if params.mode == 'script':
#         if platform_sys() == 'Windows':
#             win_cmd_head = 'python ' + ospath.join(proj_dir, 'src', 'service.py ')
#     elif params.mode == 'exe':
#         if platform_sys() == 'Windows':
#             win_cmd_head = ospath.join(proj_dir, 'bin', 'service.exe ')
#     if platform_sys() == 'Linux':
#         from service import UnixSyncService
#         linux_service = UnixSyncService("/tmp/synchronizer.pid", stdout='/tmp/out.log', stderr='/tmp/err.log')
#     print("please select option in 10s:\n[ q: query service status, 1: start service, 2: stop service, e: exit ]")
#     while True:
#         option = get_user_input() or "e"
#         try:
#             if option == "q":
#                 if platform_sys() == 'Windows':
#                     check_service_status()
#                 elif platform_sys() == 'Linux':
#                     if linux_service.is_running():
#                         print(params.service_name + ' is running')
#                     else:
#                         print(params.service_name + ' is stopped')
#             elif option == "1":
#                 if platform_sys() == 'Windows':
#                     sys_exec(win_cmd_head + '--startup=auto install')
#                     sys_exec(win_cmd_head + 'start')
#                     check_service_status()
#                     pass
#                 elif platform_sys() == 'Linux':
#                     linux_service.start()
#                     pass
#             elif option == "2":
#                 if platform_sys() == 'Windows':
#                     sys_exec(win_cmd_head + 'stop')
#                     sys_exec(win_cmd_head + 'remove')
#                     check_service_status()
#                 elif platform_sys() == 'Linux':
#                     linux_service.stop()
#                     pass
#             elif option == "e":
#                 break
#             else:
#                 print("invalid input")
#                 continue
#         except Exception as ex:
#             print(str(ex))
#             break

def check_task_status():
    # return the status of scanner and server
    if platform_sys() == "Windows":
        return check_windows_task_status(SCANNER_NAME), check_windows_task_status(SERVER_NAME)
    elif platform_sys() == "Linux":
        return '', ''
    
def control_service(type=None, operation='start'):
    if type == "scanner":
        service_name = SCANNER_NAME
    elif type == "server":
        service_name = SERVER_NAME
    else:
        print("unknown type")
        return False

    if config.mode == "script":
        python_path = sys.executable
        if platform_sys() == "Windows":
            # replace to pythonw to run no window
            python_path = ospath.join(ospath.dirname(python_path), 'pythonw.exe')
        Path = python_path
        Arg = ospath.abspath('src\\start_service.py') + ' --type ' + type
    elif config.mode == "exe":
        if platform_sys() == "Windows":
            Path = ospath.abspath('bin\\start_service.exe')
            Arg = '--type ' + type
        else:
            pass
    else:
        print("unknown mode")
        return False

    if platform_sys() == "Windows":
        if operation == "start":
            return create_windows_task(service_name, Path, Arg, autostart=config.autostart)
        elif operation == "stop":
            return stop_windows_task(service_name)
    elif platform_sys == "Linux":
        pass
    else:
        print("unsupport system")
        return False

def manage_service():
    while True:
        clear_screen()
        print("\n\n================= synchronizer console =================")
        print("  [service] 1: start/stop scanner, 2: start/stop server, e: exit")
        scanner_status, server_status = check_task_status()
        print('* scanner is', scanner_status)
        print('* server  is', server_status)
        option = input()
        if option == 'e':
            break
        elif option == '1':
            if scanner_status != "running":
                # start scanner
                control_service("scanner", "start")
            else:
                control_service("scanner", "stop")
        elif option == '2':
            if server_status != "running":
                # start server
                control_service("server", "start")
            else:
                control_service("server", "stop")
        else:
            input('invalid input, press any key to continue')
            continue

def add_a_dir():
    from Synchronizer.msg import add_exist_dir
    dir_path = input('input dir path: ')
    dir_path = ospath.abspath(dir_path)
    if not ospath.isdir(dir_path):
        print('invalid dir path')
        return False
    dir_token = input('input dir token: ')
    if dir_token == "":
        # means user want to add a new dir
        if check_dir_exist(path=dir_path):
            input("dir '%s' has been registered before, add failed, press any key to continue\n" % (dir_path,))
            logger.error("dir '%s' has been registered before, add failed", dir_path)
            return False
        tmp_token = ''
        for try_time in range(5):
            tmp_token = gen_token()
            if insert_dir(path=dir_path, token=tmp_token, registered=0):
                logger.info("add local dir '%s' ok", dir_path)
                break
        if try_time == 5:
            logger.error("generate token failed")
            return False
        me_info = get_me_info()
        if not insert_user_dir(me_info['id'], get_dir_info(token=tmp_token)['id']):
            logger.error("add user-dir failed")
            return False
        sock = get_sock(config.server_addr, config.server_port)
        if not sock:
            input('can not connect to server, press any key to continue\n')
            return False
        send_msg(sock, REGISTER_DIR, u_token=me_info['token'], addition=1)
        basename = ospath.basename(dir_path)
        send_msg(sock, REGISTER_DIR, u_token=get_me_info()['token'], addition=len(basename))

        sock.sendall(basename.encode())
        msg = my_recv(sock, MSG_LEN)
        m_info = parse_msg(msg.decode())
        msg_type = m_info['type']
        d_token = m_info['addition']
        if msg_type == REGISTER_FAILED:
            logger.error("register dir '%s' failed", dir_path)
            input('register dir failed, server refused, press any key to continue\n')
            return False
        elif msg_type == REGISTER_SUCCESS:
            # register new dir
            d_id = get_dir_info(path=dir_path)['id']
            u_id = get_me_info()['id']
            if not update_dir_info(d_id, token=d_token, registered=1):
                logger.error('something wrong')
                return
            logger.info("register dir '%s' ok", dir_path)
        else:
            logger.error('known type')
    else:
        # add an exist dir
        if add_exist_dir(dir_path, dir_token):
            print('add dir ok')
            config.managed_dirs.append(dir_path)
        else:
            print('add dir failed')


def clear_screen():
    if platform_sys() == "Windows":
        sys_exec('cls')
    elif platform_sys() == "Linux":
        sys_exec('clear')

def manage_cert():
    while True:
        clear_screen()
        print('[cert] 1: set server password, 2: verify client, e: exit')
        option = input()
        try:
            if option == '1':
                set_server_password()
            elif option == '2':
                manage_verification()
            elif option == 'e':
                break
        except:
            input('invalid input, press any key to continue')
            continue  
    
def set_server_password():
    passwd = input('[set password] please input new password: ')
    sha = get_sha(type='sha256', content=passwd.encode())
    with open('cert/passwd', 'w') as f:
        f.write(sha)
    input(f"password is set to '{passwd}'")



def manage_verification():
    # this function is used to verify the identity
    # first, you must connect to server and input the password
    # second, once password is verified, you will download certification from server
    # the certification will be used to build ssl connection
    # if server changed the certification, you must verify again
    clear_screen()
    import getpass
    try:
        passwd = getpass.getpass("[verify] please input password: ")
        sock = get_sock(config.server_addr, config.verify_port)
        if verify(sock, passwd):
            input('verify identity ok, press any key to return')
        else:
            input('verify identity failed, press any key to return')
    except:
        return


def console_framework():
    while True:
        clear_screen()
        print("\n\n================= synchronizer console =================")
        print(" >> see more in https://github.com/StdBaiy/Synchronizer << ")
        print('  [console] 1: manage service, 2: manage dir, 3: manage cert, e: exit')
        option = input()
        try:
            if option == '1':
                manage_service()
            elif option == '2':
                manage_dir()
            elif option == '3':
                manage_cert()
            elif option == 'e':
                clear_screen()
                break
            else:
                raise Exception('invalid input')
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            input(str(e))
    pass

console_framework()