#!/usr/bin/env python3

import discord
import shlex
from util import sigint, shprint
import asyncio

class RHDiscord:

    def __init__(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.client = discord.Client()

        self.config={}
        with open('config') as c:
            for l in c:
                x=shlex.split(l)
                val=x[1:]
                if len(val)==1:
                    val=val[0]
                self.config[x[0]]=val

        @self.client.event
        async def on_message(message):
        #    if message.author == client.user:
        #        return

        # Private message
            try:
                message.server.name
            except:
                return

            if message.server.name==self.config['DSERV'] and message.channel.name in self.config['DCHAN']:
                shprint(message.channel.name,':',message.content)
        #        print(message.channel.name,':',message.content,'\n> ',end='')
        #        slave.emit(Payload('discord',[message.channel.name,message.content],'shell'))

        @self.client.event
        async def on_ready():
            shprint('Discord Tracker ready')
        #    print(client.user.name)
        #    print(client.user.id)
        #    print('------',flush=True)

        self.client.run(self.config['DID'],self.config['DPWD'])
