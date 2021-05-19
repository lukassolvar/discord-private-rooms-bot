from asyncio.tasks import sleep
from logging import LoggerAdapter

import discord
from discord import guild
from discord.ext import commands
from discord.utils import *

import json

from lib.Logger import *
from lib.Database import Database

class Rooms(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.db = Database()

        self.GUILD_ID = None
        self.CATEGORY_ID = None
        self.ENTRY_ROOM_ID = None
        self.COMMANDS_ROOM_ID = None
        self.AFK_ROOM_ID = None

    async def load_settings(self):
        # Settings
        self.DEFAULT_DELETE_TIME = 60

        try:

            with open("./assets/settings.json", "r", encoding="utf8") as settings:
                data = json.load(settings)

            self.GUILD_ID = data.get("GUILD_ID")
            self.CATEGORY_ID = data.get("CATEGORY_ID")
            self.ENTRY_ROOM_ID = data.get("ENTRY_ROOM_ID")
            self.COMMANDS_ROOM_ID = data.get("COMMANDS_ROOM_ID")
            self.AFK_ROOM_ID = data.get("AFK_ROOM_ID")

            logger.info("SUCCESS: Settings loaded")

        except:
            logger.error("FAILED: Couldn't load settings")
            exit()

    async def init_module(self):
        while True:
            guild_id = input("Enter GUILD ID (Server ID) of your guild: ")
            try:
                guild_id = int(guild_id)
            except:
                print("Invalid ID! ID must only contain numbers! Try again!")
                continue
            guild = discord.utils.get(self.bot.guilds, id=guild_id)
            if guild:
                print("ID OK")
            
                try:
                    print("Creating category")
                    category = await guild.create_category("Private rooms")

                    print("Creating commands channel")
                    commands_channel = await guild.create_text_channel("🔐info", category=category)

                    print("Creating entrance channel")
                    entry_channel = await guild.create_voice_channel("Create room", category=category)

                    print("Looking for AFK room")
                    if guild.afk_channel:
                        print("AFK channel found")
                    else:
                        print("No AFK channel found! Using default values")

                except:
                    print("ERROR! Check if bot has all necessary permissions to create channels!")
                    exit()
                
                try:
                    print("Saving configuration...")
                    config = {
                        "GUILD_ID": guild_id,
                        "CATEGORY_ID": category.id,
                        "ENTRY_ROOM_ID": entry_channel.id,
                        "COMMANDS_ROOM_ID": commands_channel.id,
                    }
                    if guild.afk_channel:
                        config["AFK_ROOM_ID"] = guild.afk_channel.id
                    
                    with open("./assets/settings.json", "w", encoding="utf8") as settings:
                        json.dump(config, settings)

                except:
                    print("ERROR! Could not save configuration!")
                    exit()

                print("DONE! Starting Bot ...")
                await asyncio.sleep(2)
                break
            else:
                print("Looks like BOT has not joined the server yet! Try again after bot connects to the server.")
                continue

    @commands.Cog.listener()
    async def on_ready(self):

        await self.load_settings()

        fresh = False

        if self.GUILD_ID == 0:
            await self.init_module()
            await self.load_settings()
            fresh = True

        try:
            logger.debug("Fetching server data")

            self.guild = discord.utils.get(self.bot.guilds, id=self.GUILD_ID)
            self.entry_room = discord.utils.get(self.guild.voice_channels, id=self.ENTRY_ROOM_ID)
            self.commands_room = discord.utils.get(self.guild.channels, id=self.COMMANDS_ROOM_ID)
            self.category = discord.utils.get(self.guild.channels, id=self.CATEGORY_ID)
            self.afk_room = discord.utils.get(self.guild.channels, id=self.AFK_ROOM_ID)
        
        except:
            logger.error("FAILED: Couldn't fetch server data")
            exit()

        if fresh:
            await self.generate_message()

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
    async def message(self, ctx):

        if self.commands_room.permissions_for(ctx.author).administrator:
            await self.generate_message()

        await ctx.message.delete()
            
    async def generate_message(self):
        embed = discord.Embed(title=":lock: Private rooms", description=f"Place to create a new private room or join existing one!", color=discord.Color.magenta())
            
        embed.add_field(name=":eight_spoked_asterisk: Create a new room", inline=False, value="*Connect to the voice room below to create a new private room. Bot will move you automatically.*")
        embed.add_field(name="🙋‍♂️ Joining the room", inline=False, value="`!join <@room_owner>`\n*Sends a request to join the room.*")
        embed.add_field(name=":inbox_tray: Grant access", inline=False, value="`!add <@member>` \n*Grants access to member to join the room.*")
        embed.add_field(name=":outbox_tray: Revoke access", inline=False, value="`!remove <@member>`\n*Will revoke access for member to join the room. This will also kick member from existing room.*\n")
        embed.add_field(name=":unlock: Unlock a room", inline=False, value="`!unlock`\n*Unlocks the room for everyone without needing an invite to join.*")
        embed.add_field(name=":lock: Lock a room", inline=False, value="`!lock`\n*Locks the room. Only users with invitation will be able to join. This won't remove existing members.*")
        embed.add_field(name=":x: Delete a room", inline=False, value="`!delete`\n*Delets the room. Rooms are automatically deleted when detected as empty.*")
        embed.add_field(name=":abc: Rename a room", inline=False, value="`!rename <name>`\n*Renames a room.*")
        embed.add_field(name=":crown: Change owner", inline=False, value="`!transfer <@member>`\n*Transfers ownership to other member.*\n")
        
        embed.set_footer(text="Note: Rooms are locked by default! Commands are only valid when entered in this channel. Only owner of room can change settings and add/remove members.")
        
        await self.commands_room.send(embed=embed)

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
                embed.add_field(name="Room unlocked!", inline=True, value="Anyone can join.")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
                
                logger.info(f"Unlocked room - {channel.name}")
            
            else:
                embed = discord.Embed(title=":unlock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Room is already unlocked!", inline=True, value="Anyone can join.")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
        
        await ctx.message.delete()

    @commands.command(aliases=['lock'])
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
                embed.add_field(name="Room locked!", inline=True, value="Only members with invite can join")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
                
                logger.info(f"Locked room - {channel.name}")
            
            else:
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Room is already locked!", inline=True, value="Only members with invite can join")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)

        await ctx.message.delete()

    @commands.command(aliases=['add'])
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
                embed.add_field(name="Member added!", inline=True, value=f"Room access was given to member {mentioned_member.mention}")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)

                embed = discord.Embed(title="✅ **Private rooms**", description=f"{channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Access given!", inline=True, value=f"You were given access to room!")
                embed.set_author(name=f"{self.guild.name}")
                
                try:
                    await mentioned_member.send(embed=embed, delete_after=120)
                except:
                    pass
                
                logger.info(f"Member added to room - {channel.name}")
            
            else:
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Error!", inline=True, value=f"You can add or remove members only in locked room!")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
        
        await ctx.message.delete()
    
    @commands.command(aliases=['remove'])
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
                embed.add_field(name="Member removed!", inline=True, value="Members access has been revoked!")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
                
                if mentioned_member.voice and mentioned_member.voice.channel == channel:
                    try:
                        await mentioned_member.edit(voice_channel=self.afk_room)
                    except:
                        pass
                
                logger.info(f"Member removed from room - {channel.name}")
            
            else:
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Error!", inline=True, value=f"You can add or remove members only in locked room!")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
        
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
                embed.add_field(name="Name changed!", inline=True, value="Name of the room was successfuly changed")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
            
                logger.info(f"Room name changed - {new_name}")
            
            else:
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Error!", inline=True, value="Room name cannot contain any vulgarism!")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
        
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
            embed.add_field(name="Removed!", inline=True, value="Room was successfuly deleted!")
            await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)

            self.db.delete_private_room(channel.id)
            await channel.delete(reason="Deleted by user")
        
            logger.info(f"Deleted private room - {channel.name}")

    @commands.command()
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def join(self, ctx, mentioned_member:discord.Member):
        
        member = ctx.author
        await ctx.message.delete()
        
        if self.db.is_already_owner(mentioned_member.id):
            embed = discord.Embed(title="🙋‍♂️ **Private rooms**", description=f"{member.name} wants to join the room!", color=discord.Color.magenta())
            embed.add_field(name="Accept", inline=True, value="To approve request click on reaction 👍 or to deny request click on reaction 👎")
            embed.set_footer(text="Request will expire in 2 minutes. If you deny the request, member won't be notified.")
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
                    embed.add_field(name="Access granted!", inline=True, value=f"You were given access to the room!")
                    embed.set_author(name=f"{self.guild.name}")
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
                embed.add_field(name=":x: Denied!", inline=True, value="Member is already owner of the other private room!")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
                return
            
            else:
                # Check if mentioned member is in the same channel as current owner
                if not mentioned_member.voice or mentioned_member.voice.channel != channel:
                    embed = discord.Embed(title=":lock: **Private rooms**", description=f"{member.mention} - {channel.name}", color=discord.Color.magenta())
                    embed.add_field(name=":x: Denied!", inline=True, value="Member must be present in the room!")
                    await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)
                    return
                
                # Transfer ownership and set new name
                self.db.transfer_ownership(member.id, mentioned_member.id)
                logger.info(f"Transfering ownership of room {channel.name} from {member.name} to {mentioned_member.name}")
                channel_name = f"[🔐] {mentioned_member.name}"
                await channel.edit(name=channel_name)

                # Send message to info room
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{mentioned_member.mention} - {channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Transfer successful!", inline=True, value=f"Member {mentioned_member.name} has become new owner of the room!")
                await self.commands_room.send(embed=embed, delete_after=self.DEFAULT_DELETE_TIME)

                # Send message to new owner
                embed = discord.Embed(title=":lock: **Private rooms**", description=f"{channel.name}", color=discord.Color.magenta())
                embed.add_field(name="Rights transfered!", inline=True, value=f"{member.name} transfered ownership of the room {channel.name} to you!")
                embed.set_author(name=f"{self.guild.name}")
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
                logger.debug("FAILED: Couldn't purge messages from commands room")
                pass
    
            await asyncio.sleep(10)