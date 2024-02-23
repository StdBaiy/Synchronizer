import win32com.client
from datetime import datetime, timedelta
import subprocess

def create_windows_task(task_name, path, arg, autostart=True):
    try:
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()

        root_folder = scheduler.GetFolder('\\')
        task_def = scheduler.NewTask(0)

        task_def.RegistrationInfo.Description = task_name
        task_def.Settings.Enabled = True
        task_def.Settings.Hidden = True

        triggers = task_def.Triggers
        if autostart:
            trigger1 = triggers.Create(9)  # 9 means start when login
            trigger1.Enabled = True
            trigger1.Id = 'login_trigger'

        trigger2 = triggers.Create(1)  # 1 means start once
        trigger2.StartBoundary = (datetime.now() + timedelta(seconds=5)).isoformat()  # start in 5s
        trigger2.Enabled = True
        trigger2.Id = 'now_trigger'

        actions = task_def.Actions
        action = actions.Create(0)
        action.Path = path
        action.Arguments = arg
        
        task_def.Settings.StartWhenAvailable = True
        task_def.Settings.RestartCount = 3
        task_def.Settings.RestartInterval = "PT3M"
        task_def.Settings.DisallowStartIfOnBatteries  = False
        task_def.Settings.MultipleInstances = 2  # most 1 instance
        task_def.Settings.ExecutionTimeLimit = "PT0S" # allow tasks to run continuously

        root_folder.RegisterTaskDefinition(task_name, task_def, 6, '', '', 0)
        print(f"task create ok")
        return True
    except Exception as e:
        print(f"task create failed, : {str(e)}")
        return False

def stop_windows_task(task_name):
    try:
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        root_folder = scheduler.GetFolder('\\')

        subprocess.run(["schtasks", "/end", "/tn", task_name], check=True)  # kill all instance of the task
        root_folder.DeleteTask(task_name, 0)  # delete task
        print(f"task delete ok")
        return True
    except Exception as e:
        print(f"task delete failed, : {str(e)}")
        return False
    
def check_windows_task_status(task_name):
    status_dic = ['unknown', 'disabled', 'queued', 'ready', 'running', 'suspened', 'terminated', 'deleted']
    try:
        scheduler = win32com.client.Dispatch("Schedule.Service")
        scheduler.Connect()
        root_folder = scheduler.GetFolder("\\")
        task = root_folder.GetTask(task_name)
        status = task.State
        return status_dic[status]
    except Exception:
        return 'not installed'
    
# print(check_task_status('MyTask'))
# create_windows_task('MyTask', r'D:\Anaconda\envs\sync\python.exe', r'C:\Users\stdbay\Desktop\synchronizer\src\start_service.py --type    scanner', False)