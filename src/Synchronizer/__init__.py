from os import path as ospath, chdir
from sys import executable
import yaml
from .tools import replace_sep, logger
from .params import config, global_var
import traceback

def parse_config():
    """
    parse config file and set parameters
    """
    try:
        with open("config/config.yaml", "r", encoding="utf-8") as config_file:
            cfg = yaml.safe_load(config_file)
        config.device_name = cfg["device name"] or ""
        config.managed_dirs = cfg["managed dirs"] or []
        config.file_size_limit = cfg["file size limit"] * 1024 * 1024 # MB->B
        config.quote_num_limit= cfg["quote num limit"]
        config.always_cover = cfg["always cover"]
        config.scan_frequency = cfg["scan frequency"]
        config.conn_timeout = cfg["conn timeout"]
        config.autostart = cfg["auto start"]
        
        config.server_addr = cfg["server addr"]
        config.server_port = cfg["server port"]
        config.verify_port = cfg["verify port"]
        if cfg["storage location"]:
            config.storage_location = replace_sep(cfg["storage location"])
            if not config.storage_location.endswith('/'):
                config.storage_location += "/"
        config.allow_register = cfg["allow register"]
        config.allow_verification = cfg["allow verification"]
        config.listen_num = cfg["listen num"]
        global_var.conn_pool = {}
        if config.conn_timeout <= 3:
            config.conn_timeout = 3
    except Exception as err:
        logger.error(traceback.format_exc())


exe_list = ['synchronizer.exe', 'service.exe', 'console.exe']
# executable will be '.../python.exe' if start in script mode else one of exe_list
if ospath.basename(executable) in exe_list:
    # __file__ is not aviailable after packet to exe
    # exe is in proj_dir/bin
    global_var.mode = 'exe'
    global_var.proj_dir = ospath.dirname(ospath.dirname(executable))
else:
    # __init__.py is in proj_dir/src/Synchronizer
    global_var.mode = 'script'
    global_var.proj_dir = ospath.dirname(ospath.dirname(ospath.dirname(__file__)))

if not config.storage_location:
   config.storage_location = replace_sep(ospath.join(global_var.proj_dir, 'storage')) + '/'
chdir(global_var.proj_dir)
parse_config()