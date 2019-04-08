#!/usr/bin/env python3

import cmd, readline
import shlex
from terminaltables import AsciiTable
from colorclass import Color
from api import RHAPI
from algo import RHAlgo
from util import sigint, shprint
from discordTracker import RHDiscord
from threading import Thread

def errorDec(func):
    def wrapper(*args,**kwargs):
        try:
            return func(*args,**kwargs)
        except KeyboardInterrupt as e:
            raise e
        except Exception as e:
            print(e)
            return
    wrapper.__doc__ = func.__doc__
    return wrapper

def _color(s,c):
    return Color('{{auto{}}}{}{{/auto{}}}'.format(c,str(s),c))

def _autocolor(s,n=0):
    if s in [None,'None']:
        return s
    if s in ['call','put']:
        if s=='put':
            return _color('P','red')
        else:
            return _color('C','green')
    if float(s.replace('%',''))<-n:
        return _color(s,'red')
    elif float(s.replace('%',''))>n:
        return _color(s,'green')
    else:
        return s

def _cf(s):
    if s is None:
        return "None"
    return '{:.2f}'.format(float(s))

def _cfp(s):
    return '{:+04.2f}%'.format(100*float(s))

def _squoteformat(rawdat):
    if rawdat is None:
        return
    dat=[]
    tabl=AsciiTable(dat,'-'+_color('Stocks','blue'))
    dat.append(["Symbol","Ask","Ask Vol","Bid","Bid Vol","Open","Last Trade","Change"])
    jdic={}
    for a in range(len(dat[0])):
        jdic[a]='center'
    tabl.justify_columns=jdic
    for a in rawdat:
        dat.append([
            _color(a['symbol'],'blue'),
            _color(_cf(a['ask_price']),'green'),
            _color(a['ask_size'],'green'),
            _color(_cf(a['bid_price']),'red'),
            _color(a['bid_size'],'red'),
            _cf(a['previous_close']),
            _cf(a['last_trade_price']),
            _autocolor(_cfp(float(a['last_trade_price'])/float(a['previous_close'])-1))
            ])
    print(tabl.table)

def _oquoteformat(rawdat,API):
    if rawdat is None:
        return
    dat=[]
    tabl=AsciiTable(dat,_color('Options','blue'))
    dat.append(["Symbol","T","Strike","Exp. Date"," OI ","Tick","Ask","AVol","Bid","BVol","Open","Change","PDelta","Delta","Gamma","Theta","Vega","IV"])
    jdic={}
    for a in range(len(dat[0])):
        jdic[a]='center'
    tabl.justify_columns=jdic

    underlying={}

    for a,b in rawdat:
        try:
            if float(a['adjusted_mark_price'])>float(b['min_ticks']['cutoff_price']):
                tick=b['min_ticks']['above_tick']
            else:
                tick=b['min_ticks']['below_tick']
        except:
            print("Robinhood claims that an instrument exists, but has no data for it.")
            continue

        if b['chain_symbol'] not in underlying:
            underlying[b['chain_symbol']]=float(API.stockQuote([b['chain_symbol']])[0]['last_trade_price'])
        UL=underlying[b['chain_symbol']]

        tmp=float(a['delta']) if a['delta'] else 1.0
        PD=_cf(abs(UL*tmp/float(a['adjusted_mark_price'])))

        dat.append([
            _color(b['chain_symbol'],'blue'),
            _autocolor(b['type']),
            _cf(b['strike_price']),
            b['expiration_date'],
            a['open_interest'],
            tick,
            _color(_cf(a['ask_price']),'green'),
            _color(a['ask_size'],'green'),
            _color(_cf(a['bid_price']),'red'),
            _color(a['bid_size'],'red'),
            _cf(a['previous_close_price']),
            _autocolor(_cfp(float(a['adjusted_mark_price'])/float(a['previous_close_price'])-1)),
            PD,
            _cf(a['delta']),
            _cf(a['gamma']),
            _cf(a['theta']),
            _cf(a['vega']),
            _cf(a['implied_volatility'])
            ])
    print(tabl.table)

def _orderformat(rawdat,API):
    if rawdat == ([],[]):
        return
    dat=[]
    tabl=AsciiTable(dat,'-'+_color('Queued Orders','blue'))
    dat.append(["Symbol","Side","Quantity","Type","Price","ID"])
    jdic={}
    for a in range(len(dat[0])):
        jdic[a]='center'
    tabl.justify_columns=jdic
    
    (s,o)=rawdat

    for a in s:
        info=API.getInstrumentInfo(a['instrument'])
        typ=a['type'] if a['trigger']=='immediate' else 'stop'
        if typ=='market':
            typ=_color(typ,'red')
        if typ=='limit':
            typ=_color(typ,'green')
        if typ=='stop':
            typ=_color(typ,'blue')
        dat.append([
            info,
            a['side'],
            _cf(a['quantity']),
            typ,
            _cf(a['price']),
            a['id']
        ])
    for a in o:
        for l in a['legs']:
            info=API.getInstrumentInfo(l['option'])
            typ=a['type'] if a['trigger']=='immediate' else 'stop'
            if typ=='market':
                typ=_color(typ,'red')
            if typ=='limit':
                typ=_color(typ,'green')
            if typ=='stop':
                typ=_color(typ,'blue')
            dat.append([
                ' '.join(info),
                l['side'],
                _cf(float(a['quantity'])*float(l['ratio_quantity'])),
                typ,
                _cf(a['price']),
                a['id']
            ])
    print(tabl.table) 

def _portformat(rawdat,API):
    if rawdat == ([],[]):
        return
    dat=[]
    tabl=AsciiTable(dat,'-'+_color('Portfolio','blue'))
    dat.append(["Symbol","Quantity","Avg Unit Cost","Total Cost","Total Value","Change","PChange","Position ID"])
    jdic={}
    for a in range(len(dat[0])):
        jdic[a]='center'
    tabl.justify_columns=jdic
    
    (s,o,c)=rawdat

    tvs=0

    for a in s:
        info=API.getInstrumentInfo(a['instrument'])
        quote=API.stockQuote([info])[0]
        tc = float(a['quantity'])*float(a['average_buy_price'])
        tv = float(a['quantity'])*float(quote['bid_price'])
        tvs+=tv
        dat.append([
            info,
            _cf(a['quantity']),
            _cf(a['average_buy_price']),
            _cf(tc),
            _cf(tv),
            _autocolor(_cf(tv-tc)),
            _autocolor(_cfp(tv/tc-1)),
            a['url'].split('/')[-2]
        ])
    for a in o:
        info=API.getInstrumentInfo(a['option'])
        quote=next(API.optionQuote([info]))[0]
        tc = float(a['quantity'])*float(a['average_price'])
        tv = float(a['quantity'])*float(quote['bid_price'])*float(a['trade_value_multiplier'])
        tvs+=tv
        dat.append([
            ' '.join(info),
            _cf(a['quantity']),
            _cf(a['average_price']),
            _cf(tc),
            _cf(tv),
            _autocolor(_cf(tv-tc)),
            _autocolor(_cfp(tv/tc-1)),
            a['url'].split('/')[-2]
        ])
    dep=float(c['dep'])
    cash=float(c['cash'])
    tot=cash+tvs
    dat.append(['Cash','','',_cf(dep),_cf(cash),_autocolor(_cf(cash-dep)),_autocolor(_cfp(cash/dep-1))])
    dat.append(['Total','','',_cf(dep),_cf(tot),_autocolor(_cf(tot-dep)),_autocolor(_cfp(tot/dep-1))])
    print(tabl.table)

def _watchformat(rawdat,API):
    if rawdat=={}:
        return
    dat=[]
    tabl=AsciiTable(dat,'-'+_color('Watchlist','blue'))
    dat.append(["Symbol","Price","5s","20s","60s","Rec. Call","C Ask","C Bid","Rec. Put","P Ask","P Bid"])
    jdic={}
    for a in range(len(dat[0])):
        jdic[a]='center'
    tabl.justify_columns=jdic

    tmp1 = [[x,'C'] for x in rawdat]
    tmp2 = [[x,'P'] for x in rawdat]
    tmp = []
    tmp.extend(tmp1)
    tmp.extend(tmp2)
    bos=API.bestOption(tmp)

    for a in sorted(rawdat.keys()):
        dat.append([
            a,
            _cf(rawdat[a][0]),
            _autocolor(_cf(rawdat[a][1]),n=1),
            _autocolor(_cf(rawdat[a][4]),n=1),
            _autocolor(_cf(rawdat[a][12]),n=1),
            _color(bos[a+' C'][0],'green'),
            _color(_cf(bos[a+' C'][1]['ask_price']),'green'),
            _color(_cf(bos[a+' C'][1]['bid_price']),'red'),
            _color(bos[a+' P'][0],'red'),
            _color(_cf(bos[a+' P'][1]['ask_price']),'green'),
            _color(_cf(bos[a+' P'][1]['bid_price']),'red'),
        ])
    print(tabl.table)

class RHShell(cmd.Cmd):
    intro = 'This is a Robinhood shell. Type help for help.\n'
    prompt = '> '
    config = {}
    
    def __init__(self):
        cmd.Cmd.__init__(self)

        with open('config') as c:
            for l in c:
                x=shlex.split(l)
                self.config[x[0]]=x[1]

        Thread(target=lambda: RHDiscord(),daemon=True).start()

        self.API = RHAPI()
        self.API.login(self.config['RHID'],self.config['RHPWD'])

        self.algo = RHAlgo(self,self.API,self.config)
        Thread(target=lambda: self.algo.listen(),daemon=True).start()

    @errorDec
    def recvcmd(self,line):
        lc=self.lastcmd
        print('')
        self.onecmd(line)
        self.lastcmd=lc
        shprint('')

    @errorDec
    def do_q(self,line):
        'Query instrument prices. q <symbols>. Options symbols are formatted \"<symbol> <C/P> <strike> <YYYY-mm-dd>\".'
        ments = shlex.split(line)
        if len(ments)==0:
            print("No arguments provided.")
            return
        stocks=[]
        options=[]
        for a in ments:
            a.strip('\"').strip('\'')
            parts=a.split()
            parts = [x.upper() for x in parts]
            if len(parts)==1:
                stocks.append(parts[0])
            else:
                options.append(parts)
        _squoteformat(self.API.stockQuote(stocks))
        _oquoteformat(self.API.optionQuote(options),self.API)

    @errorDec
    def do_o(self,line):
        'Open order. o "<symbol> <side> <quantity> <price>". Example: o "SPY buy 10 250.00" "\'SPY C 250 2020-12-18\' buy 1 20.0"'
        ments = shlex.split(line)
        if len(ments)==0:
            print("No arguments provided.")
            return
        ments = [[[z.upper() for z in shlex.split(y)] if i==0 else y.upper() for i,y in enumerate(shlex.split(x))] for x in ments]
        stocks=[]
        options=[]
        for a in ments:
            if len(a[0])==1:
                a[0]=a[0][0]
                stocks.append(a)
            else:
                a[0][2]='{:.2f}'.format(float(a[0][2]))
                options.append(a)
        _orderformat((self.API.stockOpen(stocks),self.API.optionOpen(options)),self.API)

    @errorDec
    def do_c(self,line):
        'Closes positions by id. c <ID> <price>'
        args=shlex.split(line)
        args=[shlex.split(x) for x in args]
        _orderformat(self.API.closePosition(args),self.API)

    @errorDec
    def do_lo(self,line):
        'Lists unfulfilled, queued, orders'
        _orderformat(self.API.listPending(),self.API)

    @errorDec
    def do_C(self,line):
        'Cancels orders by id'
        if line=='X':
            self.API.cancelAll()
        else:
            for a in shlex.split(line):
                self.API.cancelOrder(a)

    @errorDec
    def do_p(self,line):
        'Prints current portfolio'
        _portformat(self.API.portfolio(),self.API)

    @errorDec
    def do_t(self,line):
        'test'
        self.API.test()
    
#    @errorDec
#    def do_payload(self,line):
#        'Passes a Payload onto the messagebus. <name> <data> <context>'
#        p=Payload(*shlex.split(line))
#        try:
#            self.slave.emit(p)
#        except (BrokenPipeError, AttributeError) as e:
#            print('Not connected to messagebus.')

    @errorDec
    def do_s(self,line):
        'Sets up stop order by id. <ID> <limit>'
        ments=shlex.split(line)
        if len(ments)==0:
            print('No arguments provided')
            return
        if '%' not in ments[-1]:
            price=_cf(float(ments[-1]))
        else:
            perc=1+float(ments[-1].replace('o','').replace('%',''))/100
        if '%' in ments[-1]:
            pq = self.API.positionQuote(ments[0])
            price = _cf(float(pq[1][0])*perc)
        if 'o%' in ments[-1]:
            price = _cf(float(pq[0])*perc)
        self.algo.handleStop('{}'.format(ments[0]+' '+price))

    @errorDec
    def do_w(self,line):
        'Adds instruments to watchlist'
        self.algo.handleWatch(line)
#        self.do_payload('watch \'{}\' algo'.format(line))
        pass

    @errorDec
    def do_cw(self,line):
        'Checks status of instruments off the watchlist'
        ments=shlex.split(line)
        Thread(target=lambda: self.algo.handleCW(flags=ments),daemon=True).start()
#        self.algo.handleCW(flags=ments)
#        self.do_payload('cw None algo')
        pass

    @errorDec
    def do_g(self,line):
        'Graphs an instrument off the watchlist'
        self.algo.handleGraph(line)

    def handleCW(self,data):
        _watchformat(data,self.API)
    
    @errorDec
    def do_exit(self,line):
        'Exit shell'
        self.exit()
        return True

    def exit(self):
# TO-DO: Close other services
        self.API.logout()

def main():
    rs=RHShell()
    try:
        rs.cmdloop()
    except KeyboardInterrupt:
        rs.exit()
    except:
        rs.exit()
        raise

if __name__ == '__main__':
    main()
