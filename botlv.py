import os
import random
import asyncio
import discord
import aiosqlite

from discord.ext import commands, tasks
from easy_pil import Editor, Canvas, Font, load_image_async

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")

PREFIX = "f "

LEVEL_UP_CHANNEL_ID = 1478478635491918027

# ================= INTENTS =================

intents = discord.Intents.default()

intents.message_content = True
intents.members = True
intents.voice_states = True

# ================= BOT =================

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)

# ================= DATABASE =================

async def setup_database():

    async with aiosqlite.connect("levels.db") as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            guild_id INTEGER,
            user_id INTEGER,
            text_xp INTEGER DEFAULT 0,
            voice_xp INTEGER DEFAULT 0,
            PRIMARY KEY(guild_id, user_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS level_roles(
            guild_id INTEGER,
            level INTEGER,
            role_id INTEGER
        )
        """)

        await db.commit()

# ================= LEVEL SYSTEM =================

def calculate_level(xp):

    level = 0

    while xp >= (50 * (level ** 2) + 50 * level):

        level += 1

    return level

def xp_for_next_level(level):

    return 50 * ((level + 1) ** 2) + 50 * (level + 1)

# ================= USER DATA =================

async def get_user_data(guild_id, user_id):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute(
            """
            SELECT text_xp, voice_xp
            FROM users
            WHERE guild_id=? AND user_id=?
            """,
            (guild_id, user_id)
        )

        data = await cursor.fetchone()

        if data:
            return data

        await db.execute(
            """
            INSERT INTO users(guild_id, user_id)
            VALUES(?, ?)
            """,
            (guild_id, user_id)
        )

        await db.commit()

        return 0, 0

# ================= ADD XP =================

async def add_text_xp(guild_id, user_id, amount):

    async with aiosqlite.connect("levels.db") as db:

        await db.execute(
            """
            INSERT OR IGNORE INTO users(guild_id, user_id)
            VALUES(?, ?)
            """,
            (guild_id, user_id)
        )

        await db.execute(
            """
            UPDATE users
            SET text_xp = text_xp + ?
            WHERE guild_id=? AND user_id=?
            """,
            (amount, guild_id, user_id)
        )

        await db.commit()

async def add_voice_xp(guild_id, user_id, amount):

    async with aiosqlite.connect("levels.db") as db:

        await db.execute(
            """
            INSERT OR IGNORE INTO users(guild_id, user_id)
            VALUES(?, ?)
            """,
            (guild_id, user_id)
        )

        await db.execute(
            """
            UPDATE users
            SET voice_xp = voice_xp + ?
            WHERE guild_id=? AND user_id=?
            """,
            (amount, guild_id, user_id)
        )

        await db.commit()

# ================= ROLE REWARD =================

async def give_level_roles(member, level):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute(
            """
            SELECT level, role_id
            FROM level_roles
            WHERE guild_id=?
            """,
            (member.guild.id,)
        )

        roles = await cursor.fetchall()

    for lvl, role_id in roles:

        if level >= lvl:

            role = member.guild.get_role(role_id)

            if role and role not in member.roles:

                await member.add_roles(role)

# ================= LEVEL UP =================

async def send_level_up(member, level, level_type="Text"):

    channel = member.guild.get_channel(
        LEVEL_UP_CHANNEL_ID
    )

    if not channel:
        return

    embed = discord.Embed(
        title="🎉 LEVEL UP",
        description=f"{member.mention} đã lên {level_type} Level **{level}**",
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    await channel.send(embed=embed)

# ================= MESSAGE XP =================

cooldowns = {}

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return

    cooldown_key = (
        f"{message.guild.id}-"
        f"{message.author.id}"
    )

    if cooldown_key in cooldowns:

        await bot.process_commands(message)
        return

    cooldowns[cooldown_key] = True

    old_text_xp, _ = await get_user_data(
        message.guild.id,
        message.author.id
    )

    old_level = calculate_level(old_text_xp)

    gained_xp = random.randint(15, 25)

    await add_text_xp(
        message.guild.id,
        message.author.id,
        gained_xp
    )

    new_text_xp, _ = await get_user_data(
        message.guild.id,
        message.author.id
    )

    new_level = calculate_level(new_text_xp)

    if new_level > old_level:

        await send_level_up(
            message.author,
            new_level,
            "Text"
        )

        await give_level_roles(
            message.author,
            new_level
        )

    await bot.process_commands(message)

    await asyncio.sleep(45)

    cooldowns.pop(cooldown_key, None)

# ================= VOICE XP =================

@tasks.loop(minutes=1)
async def voice_xp_task():

    for guild in bot.guilds:

        for voice_channel in guild.voice_channels:

            for member in voice_channel.members:

                if member.bot:
                    continue

                _, old_voice_xp = await get_user_data(
                    guild.id,
                    member.id
                )

                old_level = calculate_level(old_voice_xp)

                gained_xp = random.randint(10, 20)

                await add_voice_xp(
                    guild.id,
                    member.id,
                    gained_xp
                )

                _, new_voice_xp = await get_user_data(
                    guild.id,
                    member.id
                )

                new_level = calculate_level(new_voice_xp)

                if new_level > old_level:

                    await send_level_up(
                        member,
                        new_level,
                        "Voice"
                    )

# ================= RANK CARD =================

async def generate_rank_card(member):

    text_xp, voice_xp = await get_user_data(
        member.guild.id,
        member.id
    )

    text_level = calculate_level(text_xp)
    voice_level = calculate_level(voice_xp)

    next_xp = xp_for_next_level(text_level)

    current_level_xp = (
        50 * (text_level ** 2)
        + 50 * text_level
    )

    progress = (
        (text_xp - current_level_xp)
        /
        (next_xp - current_level_xp)
    )

    background = Editor(
        Canvas((900, 300), color="#1e1f22")
    )

    avatar = await load_image_async(
        str(member.display_avatar.url)
    )

    avatar = (
        Editor(avatar)
        .resize((150, 150))
        .circle_image()
    )

    background.paste(avatar, (40, 75))

    background.text(
        (230, 40),
        member.name,
        font=Font.poppins(size=40),
        color="white"
    )

    background.text(
        (230, 110),
        f"Text Level: {text_level}",
        font=Font.poppins(size=28),
        color="white"
    )

    background.text(
        (230, 160),
        f"Voice Level: {voice_level}",
        font=Font.poppins(size=28),
        color="white"
    )

    background.rectangle(
        (230, 230),
        width=550,
        height=35,
        color="#2f3136"
    )

    background.rectangle(
        (230, 230),
        width=int(550 * progress),
        height=35,
        color="#5865F2"
    )

    file = discord.File(
        fp=background.image_bytes,
        filename="rank.png"
    )

    return file

# ================= COMMANDS =================

@bot.command()
async def rank(ctx, member: discord.Member = None):

    if member is None:
        member = ctx.author

    file = await generate_rank_card(member)

    await ctx.send(file=file)

@bot.command()
async def toptext(ctx):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT user_id, text_xp
        FROM users
        WHERE guild_id=?
        ORDER BY text_xp DESC
        LIMIT 10
        """, (ctx.guild.id,))

        rows = await cursor.fetchall()

    if not rows:

        return await ctx.send(
            "Chưa có dữ liệu level."
        )

    embed = discord.Embed(
        title="🏆 TOP TEXT",
        color=discord.Color.blue()
    )

    for i, (user_id, xp) in enumerate(rows, start=1):

        member = ctx.guild.get_member(user_id)

        if member is None:
            continue

        level = calculate_level(xp)

        embed.add_field(
            name=f"#{i} • {member.name}",
            value=f"Level: {level}\nXP: {xp}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command()
async def topvoice(ctx):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT user_id, voice_xp
        FROM users
        WHERE guild_id=?
        ORDER BY voice_xp DESC
        LIMIT 10
        """, (ctx.guild.id,))

        rows = await cursor.fetchall()

    if not rows:

        return await ctx.send(
            "Chưa có dữ liệu voice."
        )

    embed = discord.Embed(
        title="🎤 TOP VOICE",
        color=discord.Color.purple()
    )

    for i, (user_id, xp) in enumerate(rows, start=1):

        member = ctx.guild.get_member(user_id)

        if member is None:
            continue

        level = calculate_level(xp)

        embed.add_field(
            name=f"#{i} • {member.name}",
            value=f"Level: {level}\nXP: {xp}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setrole(ctx, level: int, role: discord.Role):

    async with aiosqlite.connect("levels.db") as db:

        await db.execute(
            """
            INSERT INTO level_roles(
                guild_id,
                level,
                role_id
            )
            VALUES(?, ?, ?)
            """,
            (
                ctx.guild.id,
                level,
                role.id
            )
        )

        await db.commit()

    await ctx.send(
        f"Đã set role {role.name} cho level {level}"
    )

# ================= SLASH COMMAND =================

@bot.tree.command(
    name="rank",
    description="Xem rank"
)
async def slash_rank(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    if member is None:
        member = interaction.user

    file = await generate_rank_card(member)

    await interaction.response.send_message(
        file=file
    )

# ================= READY =================

@bot.event
async def on_ready():

    print(f"Online: {bot.user}")

    await setup_database()

    if not voice_xp_task.is_running():
        voice_xp_task.start()

    try:

        synced = await bot.tree.sync()

        print(f"Slash synced: {len(synced)}")

    except Exception as error:

        print(error)

# ================= RUN =================

bot.run(TOKEN)
