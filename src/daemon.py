#!/usr/bin/env python3
'''
this module is used to implement a daemon in Unix-liked system
'''
from sys import stderr, stdin, stdout, exit
from os import fork, chdir, setsid, umask, dup2, getpid, path as ospath, remove
from atexit import register
from psutil import pid_exists, Process

class Daemon:
    '''
    implement a daemon in Unix-liked system
    '''
    def __init__(self, pidfile, name='process', stdin='/dev/null', stdout='/dev/null', stderr='/dev/null', args=None):
        self.name = name
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile
        self.args = args

    def read_pid(self):
        try:
            pf = open(self.pidfile, 'r', encoding='utf-8')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        except Exception as e:
            pid = None
            print(str(e))
        return pid

    def is_running(self):
        pid = self.read_pid()
        if pid and pid_exists(pid): return True
        return False

    def daemonize(self):
        try:
            pid = fork()
            if pid > 0:
                # exit first parent
                return
        except OSError as e:
            stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            exit(1)
        # decouple from parent environment
        chdir("/")
        setsid()
        umask(0)

        # do second fork
        try:
            pid = fork()
            if pid > 0:
                # exit from second parent
                exit(0)
        except OSError as e:
            stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            exit(1)

        # redirect standard file descriptors
        with open('/tmp/1', 'w') as f:
            f.write('ok')
        stdout.flush()
        stderr.flush()
        std_in = open(self.stdin, 'r', encoding="utf-8")
        std_out = open(self.stdout, 'a+', encoding="utf-8")
        std_err = open(self.stderr, 'ab+', 0) #注意需要修改
        dup2(std_in.fileno(), stdin.fileno())
        dup2(std_out.fileno(), stdout.fileno())
        if self.stderr:
            dup2(std_err.fileno(), stderr.fileno())

        # write pidfile
        register(self.delpid)
        pid = str(getpid())
        with open(self.pidfile, 'w+', encoding="utf-8") as f:
            f.write("%s\n" % pid)
        self.run()

    def delpid(self):
        remove(self.pidfile)

    def start(self):
        # check for a pidfile to see if the daemon already runs
        if self.is_running():
            print(self.name, 'is already running')
            return
        # start the daemon
        print(self.name, 'is now running')
        self.daemonize()

    def stop(self):
        # get the pid from the pidfile
        pid = self.read_pid()
        if not self.is_running():
            print(self.name, 'is already stopped')
            if ospath.exists(self.pidfile):
                remove(self.pidfile)
            return  # not an error in a restart

        # try to kill the daemon process
        try:
            p = Process(pid)
            p.terminate()
            print(self.name, 'is now stopped')
        except Exception as err:
            print(err)

    def run(self):
        """
        You should override this method when you subclass Daemon. It will be called after the process has been
        daemonized by start() or restart().
        """