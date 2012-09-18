import os
import sys
import time
import select
import subprocess
import fcntl

def mkdirs(path):
    ''' the equivalent of mkdir -p path'''
    if os.path.exists(path):
        return
    path = os.path.normpath(path)
    items = path.split('/')
    p = ''
    for item in items:
        p += '/' + item
        if not os.path.isdir(p):
            os.mkdir(p)
            
def ask_user(prompt, can_be_empty=False, variants=None):
    while True:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        res = sys.stdin.readline()
        res = res.strip()
        if not can_be_empty and not res:
            continue
        
        if variants:
            if res in variants:
                break
            else:
                continue
        break
        
    return res

class CommandTimeoutExpired(Exception):
    pass

class ReturnCodeNotZero(Exception):
    def __init__(self, message, code):
        super(ReturnCodeNotZero, self).__init__(message)
        self.code = code
        
def get_project_name():
    try:
        output = execute_command(['git', 'remote', 'show', 'origin', '-n'])

        for line in output.split('\n'):
            if line.startswith('  Fetch URL:'):
                project_name = line.split('/')[-1][:-4]
                owner_name = line.split('/')[-2]
                return (owner_name, project_name)
        return None
    except ReturnCodeNotZero:
        return None
        
def execute_command(command, log=None, shell=False, cwd=None, timeout=0, raiseExc=True, print_to_stdout=False, exit_on_error=False):
    output = ""
    start = time.time()
    try:
        child = None
        if log:
            log.debug("Executing command: %s" % command)
        child = subprocess.Popen(
            command,
            shell=shell,
            bufsize=0, close_fds=True,
            stdin=open("/dev/null", "r"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
            )
        # use select() to poll for output so we dont block
        output = logOutput([child.stdout, child.stderr],
                start, timeout, print_to_stdout=print_to_stdout)
    except:
        # kill children if they arent done
        if child is not None and child.returncode is None:
            os.killpg(child.pid, 9)
        try:
            if child is not None:
                os.waitpid(child.pid, 0)
        except:
            pass
        raise
    
    # wait until child is done, kill it if it passes timeout
    niceExit=1
    while child.poll() is None:
        if (time.time() - start)>timeout and timeout!=0:
            niceExit=0
            os.killpg(child.pid, 15)
        if (time.time() - start)>(timeout+1) and timeout!=0:
            niceExit=0
            os.killpg(child.pid, 9)
    if not niceExit and raiseExc:
        raise CommandTimeoutExpired("Timeout(%s) expired for command:\n # %s\n%s" % (timeout, command, output))
    
    if log:
        log.debug("Child returncode was: %s" % str(child.returncode))
    if child.returncode:
        if exit_on_error:
            exit(child.returncode)
        if raiseExc:
            raise ReturnCodeNotZero("Command failed.\nReturn code: %s\nOutput: %s" % (child.returncode, output), child.returncode)
        
    return output
    
def logOutput(fds, start=0, timeout=0, print_to_stdout=False):
    done = 0
    output = ''
    
    # set all fds to nonblocking
    for fd in fds:
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if not fd.closed:
            fcntl.fcntl(fd, fcntl.F_SETFL, flags| os.O_NONBLOCK)
       
    while not done:
        if (time.time() - start)>timeout and timeout!=0:
            done = 1
            break

        i_rdy,o_rdy,e_rdy = select.select(fds,[],[],1)
        for s in i_rdy:
            # slurp as much input as is ready
            string = s.read()
            if string == '':
                done = 1
                continue
            else:
                if print_to_stdout:
                    print string
            output += string
    return output