#!/usr/bin/env python3

import shlex
from util import bell, sigint, shprint
from api import RHAPI, _rebuildOption
from time import sleep
from threading import Thread
from collections import defaultdict, deque
from statistics import stdev
import termplot
from colorclass import Color

def der(RAW):
    def oper(z,y,x):
        return (3*x-4*y+z)/2
    l=list(map(oper,RAW[2:],RAW[1:-1],RAW[:-2]))
    return l

def der2(RAW):
    try:
        ret=der(der(RAW))[0]
        if ret==[]:
            ret=None
    except IndexError:
        ret=None
    return ret

class RHAlgo():

    def __init__(self,shell,API,config):
        self.config = config
        self.API = API
        self.shell = shell

        self.stops={}
        self.watch=defaultdict(lambda: deque(maxlen=5*12+1))
        self.watchdata=[defaultdict(lambda: deque(maxlen=15*12)),defaultdict(lambda: deque(maxlen=15*12)),defaultdict(lambda: deque(maxlen=15*12))]
        self.watchsd=[defaultdict(lambda: [None]*3),defaultdict(lambda: [None]*3),defaultdict(lambda: [None]*3)]

    def listen(self):
        self.initWatch()

    def handleStop(self,data):
        [pos,price]=shlex.split(data)
        x=self.stops.get(pos,{})
        if price in x:
            shprint('Stop order already set up at this price')
            return
        def dowork():
            while True:
                sleep(int(self.config['MT']))
                (_,(bid,ask))=self.API.positionQuote(pos)
                if float(bid)<price:
                    shprint('Executing stop order\a')
                    cmdstr='c \'{} {}\''.format(pos,price)
                    self.shell.recvcmd(cmdstr)
# TO-DO: Fix
# This only works for options
# And it works badly
                    while True:
                        sleep(5)
                        (_,(bid,ask))=self.API.positionQuote(pos)
                        tmp=self.API.getPosition(pos)
                        q=int(float(tmp[0]['pending_sell_quantity']))+int(float(tmp[0]['pending_buy_quantity']))
                        if q>0:
                            shprint('Repricing stop order')
#                            cmdstr='C {}'.format(pos)
                            cmdstr='C X'
                            self.shell.recvcmd(cmdstr)
                            sleep(3)
                            cmdstr='c \'{} {}\''.format(pos,bid)
                            self.shell.recvcmd(cmdstr)
                        else:
                            break
                    return
        t=Thread(target=dowork,daemon=True)
        x[price]=t
        price=float(price)
        t.start()

    def handleWatch(self,data):
        l = shlex.split(data)
        for symb in l:
            if symb in self.watch:
                shprint('{} already being watched'.format(symb))
                continue
            self.watch[symb.upper()]=deque(maxlen=5*12+1)
        for symb in shlex.split(self.config['WATCH']):
            if symb not in self.watch:
                self.watch[symb.upper()]=deque(maxlen=5*12+1)
            

    def initWatch(self):
        def calcSD(q,sd,n):
            l = [x for x in list(q) if x is not None]
            if len(l)<24:
                return (1000,n)
            elif len(l)<len(q):
                return (float(self.config['NSD'])*stdev(l),n)
            elif len(l)==len(q):
                if n<12:
                    return (sd,n+1)
                else:
                    return (float(self.config['NSD'])*stdev(l),0)

        def dowork():
            nsd=[defaultdict(lambda: 0),defaultdict(lambda: 0),defaultdict(lambda: 0)]
            while True:
                sleep(int(self.config['DMT']))
                stocks=[]
                options=[]
                if not self.watch:
                    continue
                for a in self.watch:
                    parts=a.split()
                    if len(parts)==1:
                        stocks.append(parts[0])
                    else:
                        options.append(parts)
                s = self.API.stockQuote(stocks)
                s = {x['symbol']:float(x['last_trade_price']) for x in s} if s is not None else {}
                o = self.API.optionQuote(options)
                o = {_rebuildOption(x[1]):float(x[0]['last_trade_price']) for x in o} if o is not None else {}
                s.update(o)

                flags=[]
                for a in s:
                    self.watch[a].appendleft(s[a])
                    l0 = list(self.watch[a])

                    for b in range(3):
                        fints = lambda x: (5*x*x+x+2)//2
                        l=l0[::fints(b)]
                        tmp=der2(l[:5])
                        self.watchdata[b][a].appendleft(tmp)
                        (self.watchsd[b][a],nsd[b][a])=calcSD(self.watchdata[b][a],self.watchsd[b][a],nsd[b][a])
                        try:
                            if abs(tmp)>self.watchsd[b][a]:
                               flags.append(a)
                        except TypeError:
                            pass

                if flags:
                    bell()
                    self.handleCW(flags=flags)

        t=Thread(target=dowork,daemon=True)
        t.start()

    def handleCW(self,flags=[]):
        data={}
        if flags:
            for a in flags:
                if not self.watch[a]:
                    continue
                data[a]={0:self.watch[a][0]}
                for b in range(3):
                    fints = lambda x: (5*x*x+x+2)//2
                    tmp = self.watchdata[b][a][0]
                    data[a][fints(b)] = tmp if tmp is None else tmp/self.watchsd[b][a]
        else:
            for a in self.watch:
                if not self.watch[a]:
                    continue
                data[a]={0:self.watch[a][0]}
                for b in range(3):
                    fints = lambda x: (5*x*x+x+2)//2
                    tmp = self.watchdata[b][a][0]
                    data[a][fints(b)] = tmp if tmp is None else tmp/self.watchsd[b][a]
        self.shell.handleCW(data)

    def handleGraph(self,ID):
        if ID not in self.watch:
            print('Instrument not being watched')
        data = [x for x in list(self.watch[ID]) if x is not None]
        k=data[-1]
        data = [x/k-1 for x in data]
        data.reverse()
        s = u'\u25cf'
        c = 'blue'
        s = Color('{{auto{}}}{}{{/auto{}}}'.format(c,str(s),c))
        try:
            termplot.plot(data,plot_char=s)
        except ZeroDivisionError:
            print('No data to graph')

    def handleTest(self,p):
        with open('test2.txt','w') as o:
            print(self.watch,file=o)
        print(self.watch)

    def close(self):
        pass
