from win32serviceutil import ServiceFramework
from win32service import SERVICE_START_PENDING, SERVICE_RUNNING, SERVICE_STOP_PENDING, SERVICE_STOPPED
from win32event import CreateEvent, WaitForSingleObject, SetEvent, INFINITE
from win32api import Sleep

class Service(ServiceFramework):
    _svc_name_ = '_unNamed'
    _svc_display_name_ = '_Service Template'
    def __init__(self, *args):
        ServiceFramework.__init__(self, *args)
        self.stop_event = CreateEvent(None, 0, 0, None)
    def log(self, msg):
        import servicemanager
        servicemanager.LogInfoMsg(str(msg))
    def sleep(self, sec):
        Sleep(sec*1000, True)
    def SvcDoRun(self):
        self.ReportServiceStatus(SERVICE_START_PENDING)
        try:
            self.ReportServiceStatus(SERVICE_RUNNING)
            if self.start is not None:
                self.start()
            WaitForSingleObject(self.stop_event, INFINITE)
        except Exception:
            self.SvcStop()
    def SvcStop(self):
        self.ReportServiceStatus(SERVICE_STOP_PENDING)
        self.stop()
        SetEvent(self.stop_event)
        self.ReportServiceStatus(SERVICE_STOPPED)
    # to be overridden
    def start(self): pass
    # to be overridden
    def stop(self): pass

# def instart(cls, name, display_name=None, stay_alive=True):
#     cls._svc_name_ = name
#     cls._svc_display_name_ = display_name or name
#     try:
#         module_path = modules[cls.__module__].__file__
#     except AttributeError:
#         # maybe py2exe went by
#         from sys import executable
#         module_path = executable
#     module_file = splitext(abspath(module_path))[0]
#     cls._svc_reg_class_ = '%s.%s' % (module_file, cls.__name__)
#     if stay_alive:
#         win32api.SetConsoleCtrlHandler(lambda x: True, True)
#     try:
#         win32serviceutil.InstallService(
#             cls._svc_reg_class_,
#             cls._svc_name_,
#             cls._svc_display_name_,
#             startType=win32service.SERVICE_AUTO_START
#         )
#         print('install ok')
#     except Exception as x:
#         print(str(x))
#         print('install failed')
    # try:
    #     win32serviceutil.StartService(
    #         cls._svc_name_
    #     )
    #     print('start ok')
    # except Exception as x:
    #     print('start failed')
    #     print(str(x))
