'''
this module is used to install and start service on windows/Linux/MacOS
so that synchronizer can be control easily
'''

from platform import system
from Synchronizer.api import start_scanner, start_server
from Synchronizer.params import config, global_var

if system() == "Windows":
    from servicemanager import Initialize, PrepareToHostSingle, StartServiceCtrlDispatcher
    from win32serviceutil import HandleCommandLine
    from winservice import Service
    from sys import argv
        
    class WinSyncService(Service):
        '''
        this class is used to install and start service on windows
        once installed, it can auto start when system boot
        '''
        _svc_name_ = global_var.service_name
        _svc_display_name_ = global_var.service_name

        def start(self):
            scanner_thread = start_server()
            scanner_thread.join()

elif system() == "Linux":
    from daemon import Daemon
    class UnixSyncService(Daemon):
        def run(self):
            server_thread = start_server()
            server_thread.join()
            # with open('/tmp/test.log', 'w') as f:
            #     f.write('hello')

    # def install_service():
        #         if os.path.exists('/etc/systemd/system/synchronizer.service'):
        #             print('service already installed')
        #             return
        #         svc_content = '''[Unit]
        # Description=synchronizer service
        # After=multi-user.target
        # [Service]
        # Type=simple
        # Restart=always
        # ExecStart=/usr/bin/python3 /home/<username>/test.py
        # [Install]
        # WantedBy=multi-user.target'''
        #         with open('/etc/systemd/system/synchronizer.service', 'w') as f:
        #             f.write(svc_content)
        #         os.system('systemctl daemon-reload')
        #         os.system('systemctl enable synchronizer.service')
        # pass

    # def uninstall_service():
    #     pass

    # def lin_service_control():
    #     service = UnixSyncService("/tmp/synchronizer.pid", stdout='/tmp/out.log', stderr='/tmp/err.log')
    #     print("please select option:\n0 start service\n1 stop service\n2 query service status\n3 uninstall service\nq quit")
    #     while True:
    #         option = input()
    #         if option == "0":
    #             service.start()
    #         elif option == "1":
    #             service.stop()
    #         elif option == "2":
    #             if service.is_running():
    #                 print("synchronizer is running")
    #             else:
    #                 print("synchronizer is stopped")
    #         elif option == "3":
    #             pass
    #         elif option == "q":
    #             return
    #         else:
    #             print("invalid input")
    #             continue


if __name__ == "__main__":
    if system() == "Windows":
        if len(argv) == 1:
            Initialize()
            PrepareToHostSingle(WinSyncService)
            StartServiceCtrlDispatcher()
        else:
            HandleCommandLine(WinSyncService)
    # elif system() == "Linux":
    #     lin_service_control()