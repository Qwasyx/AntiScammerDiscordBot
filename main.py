# bot.py
import json
import os
import re
from collections import deque
from datetime import timedelta

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
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

new_members = deque()

harmful_tlds = set()
harmful_phrases = set()

json_scammer_lists = ["https://raw.githubusercontent.com/Discord-AntiScam/scam-links/main/list.json"]
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
        print("Updating harmful tlds...")
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
                        new_harmful_phrases.update(map(str.lower, text.splitlines()))

        harmful_tlds = new_harmful_tlds
        harmful_phrases = new_harmful_phrases
        print("Done updating harmful tlds...")
        await asyncio.sleep(60 * 60 * 2)  # wait for 2 hours


def is_guaranteed_harmful_message(message):
    msg = message.content
    link_regex = re.compile(r"((https?):((//)|(\\\\))+[\w\d:#@%;$()~_?+-.0-=\\.&]*/)", re.MULTILINE | re.UNICODE)
    urls = link_regex.findall(msg)
    for url in urls:
        if url[0] in harmful_tlds or (url[0] + '/') in harmful_tlds:
            return True
    return False


def is_probably_harmful_message(message):
    msg = message.content
    link_regex = re.compile(r"((https?):((//)|(\\\\))+[\w\d:#@%;$()~_?+-.0-=\\.&]*/)", re.MULTILINE | re.UNICODE)
    urls = link_regex.findall(msg)
    if len(urls) > 0:
        lower_content = message.content.lower()
        for phrase in harmful_phrases:
            if phrase in lower_content:
                return True
    return False


@client.event
async def on_ready():
    print(f'{client.user.name} has connected to Discord!')
    client.loop.create_task(update_harmful_tlds())


@client.event
async def on_message(message):
    if message.type != discord.MessageType.default:
        return
    if message.author == client.user.id:
        return

    if is_guaranteed_harmful_message(message):
        log_channel = client.get_channel(LOG_CHANNEL)
        embed = discord.Embed(title="Banned scammer", color=discord.Color.red())
        embed.add_field(name="Message", value=message.clean_content)
        embed.set_author(name=str(message.author), icon_url=message.author.avatar_url)
        embed.set_footer(text=str(message.author.id))
        await log_channel.send(embed=embed)
        await message.author.ban(delete_message_days=1, reason="Scammer (auto-detected by bot)")
    elif is_probably_harmful_message(message):
        log_channel = client.get_channel(LOG_CHANNEL)
        embed = discord.Embed(title="Deleted possible scam message and added 1hr timeout (consider banning them)", color=discord.Color.orange())
        embed.add_field(name="Message", value=message.clean_content)
        embed.set_author(name=str(message.author), icon_url=message.author.avatar_url)
        embed.set_footer(text=str(message.author.id))
        await log_channel.send(embed=embed)
        await message.author.timeout(until=timedelta(hours=24))
        await message.delete()


if __name__ == '__main__':
    client.run(TOKEN)
