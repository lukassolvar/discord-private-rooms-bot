from logging import LoggerAdapter

import discord
from discord.ext import commands
from discord.utils import *

import os
from dotenv import load_dotenv

from lib.Logger import *
from lib.Database import Database

# Settings
DEFAULT_DELETE_TIME = 60

try:
    load_dotenv()
    GUILD_ID = int(os.getenv("GUILD_ID"))
    CATEGORY_ID = int(os.getenv("CATEGORY_ID"))
    ENTRY_ROOM_ID = int(os.getenv("ENTRY_ROOM_ID"))
    COMMANDS_ROOM_ID = int(os.getenv("COMMANDS_ROOM_ID"))
    AFK_ROOM_ID = int(os.getenv("AFK_ROOM_ID"))
    logger.info("SUCCESS: Settings loaded")

except:
    logger.error("FAILED: Couldn't load settings")
    exit()
    
class Rooms(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.db = Database()

    @commands.Cog.listener()
    async def on_ready(self):

        try:
            logger.debug("Fetching server data")

            self.guild = discord.utils.get(self.bot.guilds, id=GUILD_ID)
            self.entry_room = discord.utils.get(self.guild.voice_channels, id=ENTRY_ROOM_ID)
            self.commands_room = discord.utils.get(self.guild.channels, id=COMMANDS_ROOM_ID)
            self.category = discord.utils.get(self.guild.channels, id=CATEGORY_ID)
            self.afk_room = discord.utils.get(self.guild.channels, id=AFK_ROOM_ID)
        
        except:
            logger.error("FAILED: Couldn't fetch server data")
            exit()

        game = discord.Game("Monitoring private rooms")
        await self.bot.change_presence(status=discord.Status.online, activity=game)
        
        logger.info(f'{self.bot.user.name} has connected to {self.guild.name}!')

        await self.check_rooms()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        
        # Check if user has joined entry room
        if(before.channel != self.entry_room and after.channel == self.entry_room):

            if self.db.is_already_owner(member.id):
                channel_id = self.db.get_owner_room(member.id)
                channel = discord.utils.get(self.guild.channels, id=channel_id)
                await member.edit(voice_channel=channel)
                return
            
            # Create new private room
            overwrites = {
                self.guild.default_role : discord.PermissionOverwrite(connect=False),
                member : discord.PermissionOverwrite(connect=True),
            }
            
            bitrates = [96000, 128000, 256000, 384000]
            bitrate = bitrates[self.guild.premium_tier]

            channel_name = f"[🔐] {member.name}"
            channel = await self.guild.create_voice_channel(channel_name, bitrate=bitrate, overwrites=overwrites, category=self.category)
            self.db.add_private_room(channel.id, member.id)

            # Move member to newly created room
            await member.edit(voice_channel=channel)

            logger.info(f"Created private room {channel.name}")
    
    @commands.command()
    async def generate_message(self, ctx):

        if self.commands_room.permissions_for(ctx.author).administrator:
            
            embed = discord.Embed(title=":lock: Private rooms", description=f"Place to create your own private room!", color=discord.Color.magenta())
            
            embed.add_field(name=":eight_spoked_asterisk: Vytvorenie súkromnej miestnosti", inline=False, value="*Pre vytvorenie sa pripoj do miestnosti nižšie a bot ťa automaticky presunie do tvojej novej miestnosti*")
            embed.add_field(name=":x: Zrušenie miestnosti", inline=False, value="`!delete`\n*Miestnosti sa taktiež rušia automaticky ak je daná miestnosť prázdna*")
            embed.add_field(name=":abc: Premenovanie miesnosti", inline=False, value="`!rename meno`\n*Premenuje miestnosť*")
            embed.add_field(name="🙋‍♂️ Pripojenie sa do miestnosti", inline=False, value="`!join @vlastník_miestnosti`\n*Pošle požiadavku pre pripojenie sa do miestnosti*")
            embed.add_field(name=":unlock: Otvorenie miesnosti", inline=False, value="`!unlock`\n*Odomkne miestnosť pre každého bez nutnosti pozvánky*")
            embed.add_field(name=":lock: Zavretie miesnosti", inline=False, value="`!lock`\n*Zamkne miestnosť. Ľudia s pozvánkou sa však budú môcť naďalej pripojiť*")
            embed.add_field(name=":inbox_tray: Pridelenie prístupu", inline=False, value="`!add @používateľ` \n*Pridelí prístup do miestnosti pre označeného používateľa*")
            embed.add_field(name=":outbox_tray: Zrušenie prístupu", inline=False, value="`!kick @používateľ`\n*Odoberie prístup do miestnosti pre označeného používateľa*\n")
            embed.add_field(name=":crown: Zmena majiteľa", inline=False, value="`!transfer @používateľ`\n*Zmení majiteľa miestnosti*\n")
            embed.add_field(name="💎 VIP", inline=False, value="`!vip`\n*Pridelí prístup všetkým VIP členom*\n")
            
            embed.set_footer(text="Pozn.: Miestnosti sú pri vytvorení zamknuté! Pre použitie príkazov musíš byť pripojený vo svojej miestnosti. Príkazy sú platné len ak ich zadá majiteľ miestnosti!")
            
            await self.commands_room.send(embed=embed)
        
        await ctx.message.delete()

    @commands.command(aliases=['unlock'])
    async def open(self, ctx):
        
        member = ctx.author
        channel = member.voice.channel
        
        if self.db.is_owner(channel.id, member.id):
            
            if not self.db.is_open(channel.id):
                overwrite = {
                    member : discord.PermissionOverwrite(connect=True),
                    self.guild.default_role : discord.PermissionOverwrite(connect=True)
                }

                invited_members = self.db.get_all_invited_members(channel.id)
                if invited_members:
                    for item in invited_members:
                        invited_member = discord.utils.get(self.guild.members, id=item[2])
                        overwrite.update({
                            invited_member : discord.PermissionOverwrite(connect=True)
                        })

                self.db.open_room(channel.id)
                
                await channel.edit(overwrites=overwrite)
                embed = discord.Embed(title=":unlock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Miestnosť je odomknutá!", inline=True, value="Ktokoľvek sa môže pripojiť")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
                
                logger.info(f"Unlocked room - {channel.name}")
            
            else:
                embed = discord.Embed(title=":unlock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Miestnosť už je otvorená!", inline=True, value="Ktokoľvek sa môže pripojiť")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
        
        await ctx.message.delete()

    @commands.command(aliases=['private', 'lock'])
    async def close(self, ctx):

        member = ctx.author
        channel = member.voice.channel

        if self.db.is_owner(channel.id, member.id):

            if self.db.is_open(channel.id):
                overwrite = {
                    member : discord.PermissionOverwrite(connect=True),
                    self.guild.default_role : discord.PermissionOverwrite(connect=False)
                }

                invited_members = self.db.get_all_invited_members(channel.id)
                if invited_members:
                    for item in invited_members:
                        invited_member = discord.utils.get(self.guild.members, id=item[2])
                        overwrite.update({
                            invited_member : discord.PermissionOverwrite(connect=True)
                        })

                self.db.close_room(channel.id)
                await channel.edit(overwrites=overwrite)
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Miestnosť je zamknutá!", inline=True, value="Pripojiť sa môžu len ľudia s pozvánkou")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
                
                logger.info(f"Locked room - {channel.name}")
            
            else:
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Miestnosť uz je zamknutá!", inline=True, value="Pripojiť sa môžu len ľudia s pozvánkou")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)

        await ctx.message.delete()

    @commands.command(aliases=['add', 'allow'])
    async def invite(self, ctx, mentioned_member:discord.Member):
        
        member = ctx.author
        channel = member.voice.channel
        
        if self.db.is_owner(channel.id, member.id):
            if not self.db.is_open(channel.id):
                overwrite = {
                    member : discord.PermissionOverwrite(connect=True),
                    self.guild.default_role : discord.PermissionOverwrite(connect=False)
                }

                invited_members = self.db.get_all_invited_members(channel.id)
                if invited_members:
                    for item in invited_members:
                        invited_member = discord.utils.get(self.guild.members, id=item[2])
                        overwrite.update({
                            invited_member : discord.PermissionOverwrite(connect=True)
                        })
                overwrite.update({
                        mentioned_member : discord.PermissionOverwrite(connect=True)
                })

                self.db.invite_member(channel.id, mentioned_member.id)
                await channel.edit(overwrites=overwrite)
                
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Používateľ pridaný!", inline=True, value=f"Používateľovi {mentioned_member.mention} bol pridelený prístup do miestnosti")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)

                embed = discord.Embed(title="✅ **Private rooms**", description=f"{channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Prístup udelený!", inline=True, value=f"Bol ti udelený prístup do miestnosti")
                embed.set_author(name="4R")
                
                try:
                    await mentioned_member.send(embed=embed, delete_after=120)
                except:
                    pass
                
                logger.info(f"Member added to room - {channel.name}")
            
            else:
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Chyba!", inline=True, value=f"Pridávať alebo odoberať uživateľov je možné len v zamknutej miestnosti!")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
        
        await ctx.message.delete()
    
    @commands.command(aliases=['remove', 'kick'])
    async def uninvite(self, ctx, mentioned_member:discord.Member):

        member = ctx.author
        channel = member.voice.channel

        if self.db.is_owner(channel.id, member.id):

            if not self.db.is_open(channel.id):
                overwrite = {
                    member : discord.PermissionOverwrite(connect=True),
                    self.guild.default_role : discord.PermissionOverwrite(connect=False)
                }

                invited_members = self.db.get_all_invited_members(channel.id)
                if invited_members:
                    for item in invited_members:
                        invited_member = discord.utils.get(self.guild.members, id=item[2])
                        overwrite.update({
                            invited_member : discord.PermissionOverwrite(connect=True)
                        })
                overwrite.update({
                        mentioned_member : discord.PermissionOverwrite(connect=False)
                })

                self.db.uninvite_member(channel.id, mentioned_member.id)
                await channel.edit(overwrites=overwrite)
                
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Používateľ odobratý!", inline=True, value="Používateľovi bol odobratý prístup do miestnosti")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
                
                if mentioned_member.voice.channel == channel:
                    try:
                        await mentioned_member.edit(voice_channel=self.afk_room)
                    except:
                        pass
                
                logger.info(f"Member removed from room - {channel.name}")
            
            else:
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Chyba!", inline=True, value=f"Pridávať alebo odoberať uživateľov je možné len v zamknutej miestnosti!")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
        
        await ctx.message.delete()
    
    @commands.command()
    async def rename(self, ctx, *, new_name=None):
        
        member = ctx.author
        channel = member.voice.channel
        
        if self.db.is_owner(channel.id, member.id):
            
            if new_name == None:
                await ctx.message.delete()
                return
            is_valid = True
            
            with open("./assets/bad_words.txt", "r") as file:
                words = file.readlines()
            
            for word in words:
                word = word.rstrip()
                if word in new_name.lower():
                    is_valid = False
                    break
            
            if is_valid:
                new_name = f"[{member.name}] {new_name}"
                await channel.edit(name=new_name)
            
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {new_name}", color=discord.Color.magenta())
                embed.add_field(name="Názov zmenený", inline=True, value="Názov miestnosti bol zmenený")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
            
                logger.info(f"Room name changed - {new_name}")
            
            else:
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Chyba!", inline=True, value="Názov miestnosti nesmie obsahovať žiadne vulgarizmy!")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
        
        await ctx.message.delete()

    @commands.command()
    async def delete(self, ctx):
        
        member = ctx.author
        channel = member.voice.channel
        await ctx.message.delete()
        
        if self.db.is_owner(channel.id, member.id):
            for connected_member in channel.members:
                await connected_member.edit(voice_channel=self.afk_room)

            embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
            embed.add_field(name="Odstránené!", inline=True, value="Miestnosť bola odstránená")
            await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)

            self.db.delete_private_room(channel.id)
            await channel.delete(reason="Deleted by user")
        
            logger.info(f"Deleted private room - {channel.name}")

    @commands.command()
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def join(self, ctx, mentioned_member:discord.Member):
        
        member = ctx.author
        await ctx.message.delete()
        
        if self.db.is_already_owner(mentioned_member.id):
            embed = discord.Embed(title="🙋‍♂️ **Private rooms**", description=f"{member.name} sa chce pripojiť do tvojej miestnosti", color=discord.Color.magenta())
            embed.add_field(name="Potvrdenie", inline=True, value="Ak súhlasíš klikni na reackiu 👍 v opačnom prípade na reakciu 👎")
            embed.set_footer(text="Požiadavka vyprší po 2 minútach. Odmietnutia nie sú žiadateľom oznámené.")
            embed.set_author(name=f"{member.name}")
            
            try:
                message = await mentioned_member.send(embed=embed, delete_after=120)
            except:
                pass
            await message.add_reaction("👍")
            await message.add_reaction("👎")

            def check(reaction, user):
                return user == mentioned_member and (str(reaction.emoji) == "👍" or str(reaction.emoji) == "👎")

            reaction = "👎"

            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=120.0, check=check)
            except asyncio.TimeoutError:
                await message.delete()
                self.join.reset_cooldown(ctx)
                return

            if str(reaction.emoji) != "👍":
                await message.delete()
                self.join.reset_cooldown(ctx)
                return

            await message.delete()
            channel_id = self.db.get_owner_room(mentioned_member.id)
            channel = discord.utils.get(self.guild.channels, id=channel_id)
            
            if channel:
                if not self.db.is_open(channel.id):
                    overwrite = {
                        mentioned_member : discord.PermissionOverwrite(connect=True),
                        self.guild.default_role : discord.PermissionOverwrite(connect=False)
                    }
                    invited_members = self.db.get_all_invited_members(channel.id)
                    if invited_members:
                        for item in invited_members:
                            invited_member = discord.utils.get(self.guild.members, id=item[2])
                            overwrite.update({
                                invited_member : discord.PermissionOverwrite(connect=True)
                            })
                    overwrite.update({
                        member : discord.PermissionOverwrite(connect=True)
                    })

                    self.db.invite_member(channel.id, member.id)
                    await channel.edit(overwrites=overwrite)
                    
                    embed = discord.Embed(title="✅ **Private rooms**", description=f"{channel.name}", color=discord.Color.magenta())
                    embed.add_field(name="Prístup udelený!", inline=True, value=f"Bol ti udelený prístup do miestnosti")
                    embed.set_author(name="4R")
                    try:
                        await member.send(embed=embed, delete_after=120)
                    except:
                        pass
                    
                    logger.info(f"Member added to room - {channel.name}")

            self.join.reset_cooldown(ctx)

    @commands.command()
    async def transfer(self, ctx, mentioned_member:discord.Member):

        member = ctx.author
        channel = member.voice.channel
        await ctx.message.delete()

        # Check if user is owner of the current channel
        if self.db.is_owner(channel.id, member.id):

            # Check if mentioned member is already owner of any channel
            if self.db.is_already_owner(mentioned_member.id):
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name=":x: Zamietnuté!", inline=True, value="Používateľ už je majiteľom jednej miestnosti!")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
                return
            
            else:
                # Check if mentioned member is in the same channel as current owner
                if not mentioned_member.voice or mentioned_member.voice.channel != channel:
                    embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                    embed.add_field(name=":x: Zamietnuté!", inline=True, value="Používateľ nie je prítomný v miestnosti!")
                    await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)
                    return
                
                # Transfer ownership and set new name
                self.db.transfer_ownership(member.id, mentioned_member.id)
                logger.info(f"Transfering ownership of room {channel.name} from {member.name} to {mentioned_member.name}")
                channel_name = f"[🔐] {mentioned_member.name}"
                await channel.edit(name=channel_name)

                # Send message to info room
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{mentioned_member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Zmena úspešná!", inline=True, value=f"Používateľ {mentioned_member.name} sa stal novým majiteľom miestnosti!")
                await self.commands_room.send(embed=embed, delete_after=DEFAULT_DELETE_TIME)

                # Send message to new owner
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Práva pridelené!", inline=True, value=f"{member.name} ti daroval vlastníctvo miestnosti {channel.name}")
                embed.set_author(name="4R")
                try:
                    await mentioned_member.send(embed=embed, delete_after=120)
                except:
                    pass

                logger.info(f"Transfered ownership of room - {channel.name}")

    async def check_rooms(self):

        while True:
            logger.debug("Checking rooms")

            # Get all voice channels in private rooms category
            channels_in_category = self.category.voice_channels
            for channel in channels_in_category:

                # If channel is empty, delete it
                if channel != self.entry_room and not channel.members:
                    invited_members = self.db.get_all_invited_members(channel.id)
                    if invited_members:
                        for item in invited_members:
                            self.db.uninvite_member(channel.id, item[2])
                    
                    self.db.delete_private_room(channel.id)
                    await channel.delete(reason="Empty channel")
                    
                    logger.info(f"Deleted empty private room {channel.name}")

            def is_me(m):
                return m.author != self.bot.user

            logger.debug("Purging messages from commands room")
            
            try:
                await self.commands_room.purge(limit=30, check=is_me)
            except:
                logger.error("FAILED: Couldn't purge messages from commands room")
                pass
    
            await asyncio.sleep(10)