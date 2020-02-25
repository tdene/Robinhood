#!/usr/bin/env python3

import requests
import uuid
import json
import datetime

# Reconstructs option string from instrument
def _rebuildOption(dic):
    res=[]
    res.append(dic['chain_symbol'])
    res.append(dic['type'][0].upper())
    res.append('{:.2f}'.format(float(dic['strike_price'])))
    res.append(dic['expiration_date'])
    return ' '.join(res)

# TO-DO: Make all errors this class of exception
class APIException(Exception):
    pass

def loginDec(func):
    def wrapper(*args,**kwargs):
        try:
            return func(*args,**kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code==401:
                args[0].relogin()
                return func(*args,**kwargs)
        except APIException as e:
            print(e)
            return 
    return wrapper

class RHAPI:

    ep = {
        "login": "oauth2/token/",
        "logout": "oauth2/revoke_token/",
        "investment_profile": "user/investment_profile/",
        "accounts": "accounts/",
        "ach_iav_auth": "ach/iav/auth/",
        "ach_relationships": "ach/relationships/",
        "ach_transfers": "ach/transfers/",
        "applications": "applications/",
        "dividends": "dividends/",
        "edocuments": "documents/",
        "instruments": "instruments/",
        "instruments_popularity": "instruments/popularity/",
        "margin_upgrades": "margin/upgrades/",
        "markets": "markets/",
        "notifications": "notifications/",
        "orders": "orders/",
        "password_reset": "password_reset/request/",
        "portfolios": "portfolios/",
        "positions": "positions/",
        "quotes": "marketdata/quotes/",
        "historicals": "quotes/historicals/",
        "document_requests": "upload/document_requests/",
        "user": "user/",
        "watchlists": "watchlists/",
        "news": "midlands/news/",
        "ratings": "midlands/ratings/",
        "fundamentals": "fundamentals/",
        "marketdata": "marketdata/",
        "chains":"chains/"
    }

    def _ep(self,s,opt=False):
        base_url='https://api.robinhood.com/'
        if opt:
            base_url+='options/'
        return base_url+self.ep[s]

    def __init__(self):
        self.session = requests.session()
        self.session.headers.update({
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en;q=1, fr;q=0.9, de;q=0.8, ja;q=0.7, nl;q=0.6, it;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "X-Robinhood-API-Version": "1.265.0",
            "Connection": "keep-alive",
#            "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 11895.95.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.125 Safari/537.36",
            "User-Agent": "Robinhood/823 (iPhone; iOS 7.1.2; Scale/2.00)",
            "Origin": "https://robinhood.com",
            "Referer": "https://robinhood.com/"
        })
        self.client_id = 'c82SH0WZOsabOXGP2sxqcj34FxkvfnWRZBKlBjFS'
        self.auth_token=None
        self.refresh_token=None

    def login(self, uname, pwd):
        payload = {
            'username': uname,
            'password': pwd,
            'scope': 'internal',
            'grant_type': 'password',
            'client_id': self.client_id,
            'device_token': "03856839-a0f1-4a68-bd43-62e32504fe80",
            'expires_in': 86400
        }
        req = self.session.post(self._ep('login'),data=payload)
        req.raise_for_status()
        data=req.json()

        if 'access_token' in data.keys() and 'refresh_token' in data.keys():
            self.auth_token=data['access_token']
            self.session.headers.update({'Authorization':'Bearer ' + self.auth_token})
            self.refresh_token=data['refresh_token']
            account=self.getAccount()
            self.account=account['account_number']
            self.account_url=account['url']
        else:
            print(data)
            raise Exception('Login failed')

    def relogin(self):
        payload = {
            'refresh_token': self.refresh_token,
            'scope': 'internal',
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'expires_in': 86400
        }
        req = self.session.post(self._ep('login'),data=payload)
        req.raise_for_status()
        data=req.json()

        if 'access_token' in data.keys() and 'refresh_token' in data.keys():
            self.auth_token=data['access_token']
            self.session.headers.update({'Authorization': 'Bearer ' + self.auth_token})
            self.refresh_token=data['refresh_token']
        else:
            print(data)
            raise Exception('Login failed')

# For some reason, I made the design choice to make sure
# that an account is logged in before it can be logged out
    @loginDec
    def logout(self):
        payload = {
            'client_id': self.client_id,
            'token': self.auth_token
        }
        req = self.session.post(self._ep('logout'),data=payload)
        req.raise_for_status()
        self.session.headers.update({'Authorization': None})
        self.auth_token = None

    @loginDec
    def getAccount(self):
        req = self.session.get(self._ep('accounts'))
        req.raise_for_status()
        return req.json()['results'][0]

    @loginDec
    def _handlePagination(self,req):
        res=req.json()['results']
        if req.json()['next']:
            req = self.session.get(req.json()['next'])
            res.extend(self._handlePagination(req))
        return res

# Turns stock symbol into instrument ID
    @loginDec
    def getStockID(self,stocks,flag=True):
        if not(type(stocks) is list):
            stocks=[stocks]
        res={}
        for a in stocks:
            req = self.session.get(self._ep('instruments'),params={'symbol':a})
            req.raise_for_status()
            try:
                x=req.json()['results'][0]
                res[a]=x['id']
            except:
                print('{} is not a valid Stock ticker'.format(a))
                continue
        return res

# Turns stock instrument ID into option chain ID
    @loginDec
    def getChainID(self,IDs):
        req = self.session.get(self._ep('chains',True),params={'equity_instrument_ids':','.join(IDs)})
        req.raise_for_status()
        res = self._handlePagination(req)
        return {x['symbol']:x['id'] for x in res if x['can_open_position']}

# Gets instrument IDs for constructed options
    @loginDec
    def getOptionID(self,os,flag=False):
        ress=[]
        ids=[]
        keys=list(set([x[0] for x in os]))
        oids=self.getChainID(self.getStockID([x[0] for x in os]).values())
        for o in os:
            typ=o[1]
            typ='call' if typ.lower() in ['c','call'] else typ
            typ='put' if typ.lower() in ['p','put'] else typ
            args={
                'state':'active',
#                'tradability':'tradable',
                'chain_id':oids[o[0]]
                }
            if typ!='X':
                args['type']=typ
            if o[2]!='X':
                args['strike_price']=o[2]
            if o[3]!='X':
                args['expiration_dates']=o[3]
            req = self.session.get(self._ep('instruments',True),params=args)
            req.raise_for_status()
            if req.json()['results']==[]:
                print('Option query {} is not valid'.format(' '.join(o)))
                print(req.url)
                continue
            res = self._handlePagination(req)
            res.sort(key=lambda x: (x['type'],float(x['strike_price']),x['expiration_date']))
            ress.extend(res)
        if flag:
            return ress
        else:
            return {_rebuildOption(x):x['id'] for x in ress}

# What am I doing with my life?
    @loginDec
    def getAnyID(self,IDs):
        stocks = [x for x in IDs if not isinstance(x,list)]
        options = [x for x in IDs if isinstance(x,list)]
        return {**self.getStockID(stocks), **self.getOptionID(options)}

    @loginDec
    def getInstrumentInfo(self,i):
        req = self.session.get(i)
        req.raise_for_status()
        res = req.json()
        if "options" in i:
            res['type']=res['type'][0].upper()
            res['strike_price']='{:.2f}'.format(float(res['strike_price']))
            return [res['chain_symbol'],res['type'],res['strike_price'],res['expiration_date']]
        else:
            return res['symbol']

    @loginDec
    def _instrumentQuote(self,ins,oflag=False):
        if oflag:
            url=self._ep('marketdata')+'options/'
        else:
            url=self._ep('quotes')
        req = self.session.get(url,params={'instruments':','.join(ins)})
        if req.status_code==400:
            print('All requested quote queries are invalid.')
            return
        req.raise_for_status()
        return req.json()['results']

    @loginDec
    def stockQuote(self,stocks):
        if stocks==[]:
            return
        sids=self.getStockID(stocks)
        sidurls=[self._ep('instruments')+x+'/' for x in sids.values()]
        return self._instrumentQuote(sidurls)

    @loginDec
    def optionQuote(self,options):
        if options==[]:
            return

        info=self.getOptionID(options,True)
        ress=[x['url'] for x in info]
        resss=[ress[x:x + 75] for x in range(0, len(ress), 75)]
        res=[]
        for ress in resss:
            res.extend(self._instrumentQuote(ress,True))
        if res==[]:
            print('All requested option queries are invalid.')
            return
        return zip(res,info)

    @loginDec
    def stockOpen(self,stocks):
        if stocks==[]:
            return []
        IDs=self.getStockID([x[0] for x in stocks])
        ress=[]
        for a in stocks:
            url = self._ep('instruments')+IDs[a[0]]+'/'
            payload = {
                'account':self.account_url,
                'instrument':url,
                'price':a[3] if a[3]!='X' else '0.01',
                'quantity':a[2],
                'side':a[1].lower(),
                'symbol':a[0],
                'time_in_force':'gtc',
                'trigger':'immediate',
                'type':'market' if a[3]=='X' else 'limit'
            }
            req=self.session.post(self._ep('orders'),data=payload)
            req.raise_for_status()
            ress.append(req.json())
        return ress

    @loginDec
    def optionOpen(self,options,effect='open'):
        if options==[]:
            return []
        IDs = self.getOptionID([x[0] for x in options])
        ress=[]
        for o in options:
            ID = IDs[' '.join(o[0])]
            side = o[1].lower()
            sf = side=='sell'
            direction = 'credit' if sf else 'debit'
            legs=[{
                'option':self._ep('instruments',True)+ID+'/',
                'side':side,
                'position_effect':effect,
                'ratio_quantity':'1'
            }]
            payload = {
                'account':self.account_url,
                'price':o[3] if o[3]!='X' else '0.01',
                'quantity':o[2],
                'time_in_force':'gtc',
                'trigger':'immediate',
                'type':'market' if o[3]=='X' else 'limit',
                'direction':direction,
                'legs':legs,
                'override_day_trade_checks':False,
                'override_dtbp_checks':False,
                'ref_id':str(uuid.uuid4())
            }
            self.session.headers.update({'content-type':'application/json'})
            req = self.session.post(self._ep('orders',True),json=payload)
            self.session.headers.update({"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"})
            try:
                req.raise_for_status()
            except:
                print(req.text)
            ress.append(req.json())
        return ress

    @loginDec
    def getPosition(self,ID):
        try:
            xstr='{}/{}/'.format(self.account,ID)
            req=self.session.get(self._ep('positions')+xstr)
            req.raise_for_status()
            res=req.json()
            flag=True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code!=404:
                raise e
            try:
                xstr='{}/'.format(ID)
                req=self.session.get(self._ep('positions',True)+xstr)
                req.raise_for_status()
                res=req.json()
                flag=False
            except:
                raise APIException("ERROR: Position {} cannot be found.".format(ID))
        return (res,flag)

    @loginDec
    def closePosition(self,poss):
        stocks=[]
        options=[]
        for a in poss:
            (res,flag)=self.getPosition(a[0])
            aq=int(float(res['quantity']))-int(float(res['pending_sell_quantity']))
            if aq==0:
                print("Position {} cannot be closed because you do not own any of it.".format(a[0]))
            try:
                p=a[1]
            except:
                p='X'
            if flag:
                symbol=self.getInstrumentInfo(res['instrument'])
                di='sell'
                q=aq
                stocks.append([symbol,di,q,p])
            else:
                symbol=self.getInstrumentInfo(res['option'])
                di='sell' if aq>0 else 'buy'
                q=abs(aq)
                options.append([symbol,di,q,p])
        return (self.stockOpen(stocks),self.optionOpen(options,'close'))

    @loginDec
    def listPending(self):
        req=self.session.get(self._ep('orders'))
        req.raise_for_status()
        res=self._handlePagination(req)
        s=[x for x in res if x['cancel'] is not None]
        req=self.session.get(self._ep('orders',True))
        req.raise_for_status()
        res=self._handlePagination(req)
        o=[x for x in res if x['cancel_url'] is not None]
        return (s,o)

    @loginDec
    def cancelOrder(self,x):
        url=(self._ep('orders')+x+'/cancel/',
            self._ep('orders',True)+x+'/cancel/')
        req=self.session.post(url[0])
        if(req.status_code==200):
            print("Order {} successfully canceled.".format(x))
            return
        req=self.session.post(url[1])
        if(req.status_code==200):
            print("Order {} successfully canceled.".format(x))
            return
        print("Order {} unsuccessfully canceled.".format(x))

    @loginDec
    def cancelAll(self):
        (s,o)=self.listPending()
        tmp=s
        tmp.extend(o)
        for a in tmp:
            self.cancelOrder(a['id'])

    @loginDec
    def portfolio(self):
        req=self.session.get(self._ep('positions'))
        req.raise_for_status()
        res=self._handlePagination(req)
        s=[x for x in res if float(x['quantity'])!=0]

        req=self.session.get(self._ep('positions',True))
        req.raise_for_status()
        res=self._handlePagination(req)
        o=[x for x in res if float(x['quantity'])!=0 and float(x['pending_expired_quantity'])==0]

        req=self.session.get(self._ep('accounts'))
        req.raise_for_status()
        c=req.json()['results'][0]

        url=self._ep('portfolios')+'historicals/{}/'.format(self.account)
        req=self.session.get(url,params={'bounds':'regular','span':'all'})
        req.raise_for_status()
        c['dep']=req.json()['equity_historicals'][0]['adjusted_open_equity']
        return (s,o,c)

    @loginDec
    def positionQuote(self,ID):
        (res,flag)=self.getPosition(ID)
        tvm = float(res.get('trade_value_multiplier',1))
        orig = '{:.2f}'.format(float(res['average_buy_price'] if flag else res['average_price'])/tvm)
        res = self._instrumentQuote([res['instrument']] if flag else [res['option']],not flag)[0]
        if flag:
            p='{:.2f}'.format(float(res['last_trade_price']))
            cur=(p,p)
        else:
            bp='{:.2f}'.format(float(res['bid_price']))
            ap='{:.2f}'.format(float(res['ask_price']))
            cur=(bp,ap)
        return (orig,cur)

    @loginDec
    def bestOption(self,os):
        def pickbest(qs,ul):
            mx={}
            for a,b in qs:
                if a is None:
                    continue
                i=b['chain_symbol']+' '+b['type'][0].upper()
                tmp = float(a['delta']) if a['delta'] else 1.0
                pd = abs(ul[b['chain_symbol']]*tmp/float(a['adjusted_mark_price']))
                a['pd']=pd
                if float(a['adjusted_mark_price'])>0.4 and (mx.get(i,None) is None or pd > mx[i][1]['pd']):
                    mx[i]=(_rebuildOption(b),a)
            return mx

        tdy=datetime.datetime.today()
        date=tdy+datetime.timedelta(days=(4-tdy.weekday() if tdy.weekday()<3 else 11-tdy.weekday()))
        date=date.strftime("%Y-%m-%d")

        ret={}

        underlying = {x['symbol']:float(x['last_trade_price']) for x in self.stockQuote([x[0] for x in os])}

        os = [[x[0],x[1],'X',date] for x in os]
        qs = self.optionQuote(os)

        return pickbest(qs,underlying)

    @loginDec
    def test(self):
        pass
