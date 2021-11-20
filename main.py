# bot.py
import json
import os
import re
from collections import deque
from datetime import datetime

import aiohttp
import asyncio
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
SEND_ERRORS_TO = int(os.getenv('SEND_ERRORS_TO'))
LOG_CHANNEL = int(os.getenv('LOG_CHANNEL'))


intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

new_members = deque()

harmful_tlds = set()
harmful_phrases = set()

json_scammer_lists = ["https://raw.githubusercontent.com/Discord-AntiScam/scam-links/main/urls.json"]
plain_scammer_lists = ["https://raw.githubusercontent.com/BuildBot42/discord-scam-links/main/list.txt",
                       "https://raw.githubusercontent.com/Qwasyx/DiscordScamDetectionList/main/known-scammer-domains.txt"]

plain_keyword_lists = ["https://raw.githubusercontent.com/Qwasyx/DiscordScamDetectionList/main/known-scammer-phrases.txt"]


async def send_error(msg):
    user = client.get_user(SEND_ERRORS_TO)
    await user.create_dm()
    await user.dm_channel.send("Error: " + msg)


async def update_harmful_tlds():
    global harmful_tlds, harmful_phrases
    while True:
        new_harmful_tlds = set()
        new_harmful_phrases = set()
        async with aiohttp.ClientSession() as session:
            for url in json_scammer_lists:
                async with session.get(url) as response:
                    if response.status != 200:
                        await send_error("Can't connect to {} anymore, error code {}".format(url, response.status))
                    else:
                        new_harmful_tlds.update(json.loads(await response.text()))
            for url in plain_scammer_lists:
                async with session.get(url) as response:
                    if response.status != 200:
                        await send_error("Can't connect to {} anymore, error code {}".format(url, response.status))
                    else:
                        text = await response.text()
                        for line in text.splitlines():
                            new_harmful_tlds.add('http://{}/'.format(line))
                            new_harmful_tlds.add('https://{}/'.format(line))

            for url in plain_keyword_lists:
                async with session.get(url) as response:
                    if response.status != 200:
                        await send_error(
                            "Can't connect to {} anymore, error code {}".format(url, response.status))
                    else:
                        text = await response.text()
                        new_harmful_phrases.update(text.splitlines())

        harmful_tlds = new_harmful_tlds
        harmful_phrases = new_harmful_phrases
        await asyncio.sleep(60 * 60 * 24)  # wait for 24 hours


def clean_new_members():
    now = datetime.now()
    while len(new_members) > 0 and (now - new_members[0][1]).total_seconds() > 5 * 60:
        new_members.popleft()


async def is_harmful_message(message):
    msg = message.content
    link_regex = re.compile(r"((https?):((//)|(\\\\))+[\w\d:#@%;$()~_?+-.0-=\\.&]*/)", re.MULTILINE | re.UNICODE)
    urls = link_regex.findall(msg)
    for url in urls:
        if url[0] in harmful_tlds or (url[0] + '/') in harmful_tlds:
            return True

    if len(urls) > 0:
        for phrase in harmful_phrases:
            if phrase in message.content:
                return True
    return False


@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')


@client.event
async def on_member_join(member):
    new_members.append((member.id, datetime.now()))


@client.event
async def on_message(message):
    if message.type != discord.MessageType.default:
        return
    if message.author == client.user.id:
        return

    clean_new_members()
    potential_member = discord.utils.find(lambda x: x[0] == message.author.id, new_members)

    if potential_member is None:
        return

    if await is_harmful_message(message):
        log_channel = client.get_channel(LOG_CHANNEL)
        embed = discord.Embed(title="Banned scammer", color=discord.Color.red())
        embed.add_field(name="Message", value=message.clean_content)
        embed.set_author(name=message.author.name + '#' + message.author.discriminator, icon_url=message.author.avatar_url)
        embed.set_footer(text=str(message.author.id))
        await log_channel.send(embed=embed)
        await message.author.ban(delete_message_days=1, reason="Scammer (auto-detected by bot)")

    new_members.remove(potential_member)

if __name__ == '__main__':
    client.loop.create_task(update_harmful_tlds())
    client.run(TOKEN)