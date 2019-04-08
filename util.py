#!/usr/bin/env python3

import os, signal
import sys, readline, fcntl, termios, struct

sigint=lambda x: os.kill(os.getpid(), signal.SIGINT)
#shprint=lambda *x: print(*x,'\n> ',end='')
bell=lambda: print('\a',end='')

def shprint(*x):
    line=readline.get_line_buffer()
    (r,c) = struct.unpack('hh', fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ,'____'))
    l=len(line)+2
    sys.stdout.write('\x1b[2K')
    sys.stdout.write('\x1b[1A\x1b[2K'*int(l/c))
    sys.stdout.write('\x1b[0G')
    print(*x,'\n>',line,end='',flush=True)
