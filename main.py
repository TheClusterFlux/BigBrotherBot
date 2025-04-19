import discord
from discord.ext  import commands
from discord import app_commands
import asyncio
import datetime
import os
import requests
import time
import sys
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/',intents=intents)
SQLITE_SERVICE_URL = os.getenv('SQLITE_SERVICE_URL', 'http://sqlite-service:8080')
failed_db_calls = []

async def retry_failed_db_calls():
    while True:
        for call in failed_db_calls[:]:
            try:
                response = requests.post(call['url'], json=call['data'])
                if response.status_code == 200:
                    failed_db_calls.remove(call)
                else:
                    print(f"Retry failed for call: {call}, error: {response.json().get('error')}")
            except Exception as e:
                print(f"Exception during retry: {e}")
        await asyncio.sleep(60)
        
        
async def insert_chat_instance(channel_name, start_time):
    data = {
        "query": f"INSERT INTO chat_instances (channel_name, start_time) VALUES ('{channel_name}', '{start_time.isoformat()}')"
    }
    try:
        response = requests.post(f"{SQLITE_SERVICE_URL}/execute", json=data)
        if response.status_code == 200:
            return response.json().get('lastrowid')
        else:
            if(response.json()['error'] == "no such table: chat_instances"):
                response = requests.post(f"{SQLITE_SERVICE_URL}/execute", json={
                    "query": "CREATE TABLE chat_instances (id INTEGER PRIMARY KEY, channel_name TEXT, start_time TEXT, end_time TEXT)"
                })
                if response.status_code != 200:
                    raise Exception(response.json()['error'])
                return await insert_chat_instance(channel_name, start_time)
            raise Exception(response.json()['error'])
    except Exception as e:
        print(f"Failed to insert chat instance: {e}")
        failed_db_calls.append({'url': f"{SQLITE_SERVICE_URL}/execute", 'data': data})

async def update_chat_instance(instance_id, end_time):
    data = {
        "query": f"UPDATE chat_instances SET end_time = '{end_time.isoformat()}' WHERE id = {instance_id}"
    }
    try:
        response = requests.post(f"{SQLITE_SERVICE_URL}/execute", json=data)
        if response.status_code != 200:
            raise Exception(response.json()['error'])
    except Exception as e:
        print(f"Failed to update chat instance: {e}")
        failed_db_calls.append({'url': f"{SQLITE_SERVICE_URL}/execute", 'data': data})


async def insert_chat_user(chat_instance_id, user_id):
    data = {
        "query": f"INSERT INTO chat_users (chat_instance_id, user_id) VALUES ({chat_instance_id}, {user_id})"
    }
    try:
        response = requests.post(f"{SQLITE_SERVICE_URL}/execute", json=data)
        if response.status_code != 200:
            if response.json()['error'] == "no such table: chat_users":
                response = requests.post(f"{SQLITE_SERVICE_URL}/execute", json={
                    "query": "CREATE TABLE chat_users (chat_instance_id INTEGER, user_id INTEGER)"
                })
                if response.status_code != 200:
                    raise Exception(response.json()['error'])
                return await insert_chat_user(chat_instance_id, user_id)
            raise Exception(response.json()['error'])
    except Exception as e:
        print(f"Failed to insert chat user: {e}")
        failed_db_calls.append({'url': f"{SQLITE_SERVICE_URL}/execute", 'data': data})


async def remove_chat_user(chat_instance_id, user_id):
    data = {
        "query": f"DELETE FROM chat_users WHERE chat_instance_id = {chat_instance_id} AND user_id = {user_id}"
    }
    try:
        response = requests.post(f"{SQLITE_SERVICE_URL}/execute", json=data)
        if response.status_code != 200:
            raise Exception(response.json()['error'])
    except Exception as e:
        print(f"Failed to remove chat user: {e}")
        failed_db_calls.append({'url': f"{SQLITE_SERVICE_URL}/execute", 'data': data})

    
    
async def is_user_opted_in(user_id):
    response = requests.post(f"{SQLITE_SERVICE_URL}/execute", json={
        "query": f"SELECT 1 FROM opt_in_users WHERE user_id = {user_id}"
    })
    if response.status_code == 200:
        return len(response.json().get('result', [])) > 0
    else:
        raise Exception(response.json().get('error'))
    
    
user_voice_times = {}

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    print(f"Bot status: {bot.status}")
    await bot.change_presence(activity=discord.Game(name="Tracking Voice Channel Time"))
    print(f"Bot is connected to {len(bot.guilds)} guilds.")
    guild_list = "\n".join([f"{guild.id}: {guild.name}" for guild in bot.guilds])
    print(f"Connected to guilds:\n{guild_list}")
    discord.Object(id=216499328997523456)  
    bot.tree.clear_commands(guild=bot.guilds[0])
    await bot.tree.sync(guild=bot.guilds[0])  
    print("Commands:")
    for command in await bot.tree.fetch_commands():
        print(command.name)
    await log_active_members()
    bot.loop.create_task(retry_failed_db_calls())
    print("bot is ready")
    print(bot.latency)
    sys.stdout.flush()  # Ensure logs are flushed to Kubernetes logs

async def log_active_members():
    for guild in bot.guilds:
        for member in guild.members:
            if member.voice is not None and member.voice.channel is not None:
                user_voice_times[member.id] = time.time()
                print(f"{member.name} is in voice channel {member.voice.channel.name}")

chat_instances = {}

@bot.event
async def on_voice_state_update(member, before, after):
    if not await is_user_opted_in(member.id):
        print(f"unregistered user has joined a voice channel, ignoring")
        sys.stdout.flush()  # Ensure logs are flushed to Kubernetes logs
        return

    current_time = datetime.datetime.now()

    if before.channel is None and after.channel is not None:
        print(f"{member.name} joined voice channel {after.channel.name}")
        if after.channel.id not in chat_instances:
            chat_instance_id = await insert_chat_instance(after.channel.name, current_time)
            chat_instances[after.channel.id] = {
                'id': chat_instance_id,
                'start_time': current_time,
                'users': [member.id]
            }
            await insert_chat_user(chat_instance_id, member.id)
        else:
            chat_instance_id = chat_instances[after.channel.id]['id']
            chat_instances[after.channel.id]['users'].append(member.id)
            await insert_chat_user(chat_instance_id, member.id)

    elif before.channel is not None and after.channel is None:
        print(f"{member.name} left voice channel {before.channel.name}")
        if before.channel.id in chat_instances:
            chat_instance_id = chat_instances[before.channel.id]['id']
            chat_instances[before.channel.id]['users'].remove(member.id)
            await remove_chat_user(chat_instance_id, member.id)
            if not chat_instances[before.channel.id]['users']:
                instance = chat_instances.pop(before.channel.id)
                await update_chat_instance(instance['id'], current_time)

    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        print(f"{member.name} switched from {before.channel.name} to {after.channel.name}")
        if before.channel.id in chat_instances:
            chat_instance_id = chat_instances[before.channel.id]['id']
            chat_instances[before.channel.id]['users'].remove(member.id)
            await remove_chat_user(chat_instance_id, member.id)
            if not chat_instances[before.channel.id]['users']:
                instance = chat_instances.pop(before.channel.id)
                await update_chat_instance(instance['id'], current_time)
        if after.channel.id not in chat_instances:
            chat_instance_id = await insert_chat_instance(after.channel.name, current_time)
            chat_instances[after.channel.id] = {
                'id': chat_instance_id,
                'start_time': current_time,
                'users': [member.id]
            }
            await insert_chat_user(chat_instance_id, member.id)
        else:
            chat_instance_id = chat_instances[after.channel.id]['id']
            chat_instances[after.channel.id]['users'].append(member.id)
            await insert_chat_user(chat_instance_id, member.id)
    sys.stdout.flush()  # Ensure logs are flushed to Kubernetes logs

@bot.tree.command(name="opt_in", description="opt in to the time logging system")
async def opt_in(interaction: discord.Interaction):
    user = interaction.user 
    print(f"User {user.name} opted in")
    print(user)
    user_id = user.id
    username = user.name
    discriminator = user.discriminator
    avatar_url = str(user.avatar)
    created_at = user.created_at.isoformat()
    display_name = user.display_name
    status = str(user.status)
    data = {
        "query": f"""
            INSERT OR IGNORE INTO opt_in_users 
            (user_id, username, discriminator, avatar_url, created_at, display_name, status) 
            VALUES 
            ({user_id}, '{username}', '{discriminator}', '{avatar_url}', '{created_at}', '{display_name}', '{status}')
        """
    }
    try:
        response = requests.post(f"{SQLITE_SERVICE_URL}/execute", json=data)
        if response.status_code == 200:
            await interaction.response.send_message(f"{user.name}, you have opted in to voice channel tracking.")
        elif response.json().get('error') == "no such table: opt_in_users":
            response = requests.post(f"{SQLITE_SERVICE_URL}/execute", json={
                "query": """
                    CREATE TABLE opt_in_users (
                        user_id INTEGER PRIMARY KEY, 
                        username TEXT, 
                        discriminator TEXT, 
                        avatar_url TEXT, 
                        created_at TEXT, 
                        display_name TEXT, 
                        status TEXT
                    )
                """
            })
            if response.status_code == 200:
                await opt_in(interaction)
            else:
                raise Exception(response.json()['error'])
        else:
            raise Exception(response.json().get('error'))
    except Exception as e:
        print(f"Failed to opt in: {e}")
        failed_db_calls.append({'url': f"{SQLITE_SERVICE_URL}/execute", 'data': data})
        await interaction.response.send_message(f"Failed to opt in, please try again later.")
    sys.stdout.flush()  # Ensure logs are flushed to Kubernetes logs


bot.run(TOKEN)
