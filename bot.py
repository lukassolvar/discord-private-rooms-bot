# bot.py
from logging import Logger
import discord
from discord.ext import commands
from discord.utils import *

import os
from dotenv import load_dotenv

from lib.Logger import *
from lib.Rooms import Rooms

intents = discord.Intents.default()
intents.members = True
#intents.presences = True
intents.reactions = True

try:
    load_dotenv()
    TOKEN = str(os.getenv("TOKEN"))
    logger.info("SUCCESS: Settings loaded")
except:
    logger.error("FAILED: Couldn't load settings")
    exit()

class Bot():

    def __init__(self):

        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None,  case_insensitive=True)
        self.bot.add_cog(Rooms(self.bot))

        self.bot.run(TOKEN)
Bot()