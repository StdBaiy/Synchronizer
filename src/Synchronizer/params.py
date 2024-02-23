class config:
    device_name = ''
    managed_dirs = []
    file_size_limit = 64*1024*1024
    quote_num_limit = 10
    always_cover = False
    scan_frequency = 3
    only_local = False
    conn_timeout = 60
    autostart = True

    server_addr = '127.0.0.1'
    server_port = 8088
    verify_port = 8089
    storage_location = ''
    allow_register: True
    allow_verification: True
    listen_num = 128

class global_var:
    conn_pool = {}
    mode = "script"
    proj_dir = ''
    service_name = 'synchronizer'
    server_sock = None
    test = False
    node = 'client'
    listening = True