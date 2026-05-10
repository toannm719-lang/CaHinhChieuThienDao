import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import random
import asyncio
import os

from easy_pil import Editor, Canvas, Font, load_image_async

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")

LEVEL_UP_CHANNEL_ID = 1478478635491918027

PREFIX = "f "

# ================= BOT =================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)

cooldowns = {}

# ================= DATABASE =================

async def setup_db():

    async with aiosqlite.connect("levels.db") as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS levels(
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

def get_level(xp):
    return int((xp // 100) ** 0.5)

def xp_for_next_level(level):
    return ((level + 1) ** 2) * 100

# ================= USER DATA =================

async def get_data(guild_id, user_id):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT text_xp, voice_xp
        FROM levels
        WHERE guild_id=? AND user_id=?
        """, (guild_id, user_id))

        data = await cursor.fetchone()

        if not data:

            await db.execute("""
            INSERT INTO levels(guild_id, user_id)
            VALUES(?,?)
            """, (guild_id, user_id))

            await db.commit()

            return 0, 0

        return data

# ================= ADD XP =================

async def add_text_xp(guild_id, user_id, amount):

    async with aiosqlite.connect("levels.db") as db:

        await db.execute("""
        INSERT OR IGNORE INTO levels(guild_id, user_id)
        VALUES(?,?)
        """, (guild_id, user_id))

        await db.execute("""
        UPDATE levels
        SET text_xp = text_xp + ?
        WHERE guild_id=? AND user_id=?
        """, (amount, guild_id, user_id))

        await db.commit()

async def add_voice_xp(guild_id, user_id, amount):

    async with aiosqlite.connect("levels.db") as db:

        await db.execute("""
        INSERT OR IGNORE INTO levels(guild_id, user_id)
        VALUES(?,?)
        """, (guild_id, user_id))

        await db.execute("""
        UPDATE levels
        SET voice_xp = voice_xp + ?
        WHERE guild_id=? AND user_id=?
        """, (amount, guild_id, user_id))

        await db.commit()

# ================= LEVEL UP =================

async def check_level_up(member):

    text_xp, voice_xp = await get_data(
        member.guild.id,
        member.id
    )

    level = get_level(text_xp)

    channel = member.guild.get_channel(
        LEVEL_UP_CHANNEL_ID
    )

    if channel:

        embed = discord.Embed(
            title="🎉 LEVEL UP!",
            description=(
                f"{member.mention} đã lên "
                f"level **{level}**"
            ),
            color=discord.Color.blurple()
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        await channel.send(embed=embed)

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT level, role_id
        FROM level_roles
        WHERE guild_id=?
        """, (member.guild.id,))

        data = await cursor.fetchall()

    for lvl, role_id in data:

        if level >= lvl:

            role = member.guild.get_role(role_id)

            if role:

                if role not in member.roles:

                    try:
                        await member.add_roles(role)

                    except:
                        pass

# ================= MESSAGE XP =================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return

    key = f"{message.guild.id}-{message.author.id}"

    if key in cooldowns:
        return

    cooldowns[key] = True

    async def remove_cooldown():

        await asyncio.sleep(60)

        cooldowns.pop(key, None)

    asyncio.create_task(remove_cooldown())

    xp = random.randint(15, 25)

    old_xp, _ = await get_data(
        message.guild.id,
        message.author.id
    )

    old_level = get_level(old_xp)

    await add_text_xp(
        message.guild.id,
        message.author.id,
        xp
    )

    new_xp, _ = await get_data(
        message.guild.id,
        message.author.id
    )

    new_level = get_level(new_xp)

    if new_level > old_level:

        await check_level_up(message.author)

    await bot.process_commands(message)

# ================= VOICE XP =================

@tasks.loop(minutes=1)
async def voice_task():

    for guild in bot.guilds:

        for vc in guild.voice_channels:

            for member in vc.members:

                if member.bot:
                    continue

                if member.voice.self_deaf:
                    continue

                if member.voice.afk:
                    continue

                xp = random.randint(10, 20)

                await add_voice_xp(
                    guild.id,
                    member.id,
                    xp
                )

# ================= RANK CARD =================

async def create_rank(member):

    text_xp, voice_xp = await get_data(
        member.guild.id,
        member.id
    )

    text_level = get_level(text_xp)
    voice_level = get_level(voice_xp)

    next_level_xp = xp_for_next_level(text_level)

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

    background.paste(avatar, (30, 75))

    background.text(
        (220, 40),
        member.name,
        color="white",
        font=Font.poppins(size=40)
    )

    background.text(
        (220, 120),
        f"Text Level: {text_level}",
        color="white",
        font=Font.poppins(size=30)
    )

    background.text(
        (220, 170),
        f"Voice Level: {voice_level}",
        color="white",
        font=Font.poppins(size=30)
    )

    progress = 550 * (
        text_xp / next_level_xp
    )

    background.rectangle(
        (220, 240),
        width=550,
        height=35,
        color="#2f3136"
    )

    background.rectangle(
        (220, 240),
        width=progress,
        height=35,
        color="#5865F2"
    )

    file = discord.File(
        fp=background.image_bytes,
        filename="rank.png"
    )

    return file

# ================= PREFIX COMMANDS =================

@bot.command()
async def rank(ctx, member: discord.Member = None):

    if not member:
        member = ctx.author

    file = await create_rank(member)

    await ctx.send(file=file)

@bot.command()
async def toptext(ctx):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT user_id, text_xp
        FROM levels
        WHERE guild_id=?
        ORDER BY text_xp DESC
        LIMIT 10
        """, (ctx.guild.id,))

        data = await cursor.fetchall()

    msg = "🏆 TEXT LEADERBOARD\n\n"

    for i, (user_id, xp) in enumerate(data, start=1):

        user = ctx.guild.get_member(user_id)

        if user:

            msg += (
                f"{i}. {user.name} "
                f"- Level {get_level(xp)}\n"
            )

    await ctx.send(msg)

@bot.command()
async def topvoice(ctx):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT user_id, voice_xp
        FROM levels
        WHERE guild_id=?
        ORDER BY voice_xp DESC
        LIMIT 10
        """, (ctx.guild.id,))

        data = await cursor.fetchall()

    msg = "🎤 VOICE LEADERBOARD\n\n"

    for i, (user_id, xp) in enumerate(data, start=1):

        user = ctx.guild.get_member(user_id)

        if user:

            msg += (
                f"{i}. {user.name} "
                f"- Level {get_level(xp)}\n"
            )

    await ctx.send(msg)

@bot.command()
@commands.has_permissions(administrator=True)
async def setrole(
    ctx,
    level: int,
    role: discord.Role
):

    async with aiosqlite.connect("levels.db") as db:

        await db.execute("""
        INSERT INTO level_roles(
            guild_id,
            level,
            role_id
        )
        VALUES(?,?,?)
        """, (
            ctx.guild.id,
            level,
            role.id
        ))

        await db.commit()

    await ctx.send(
        f"✅ Đã set role "
        f"{role.name} cho level {level}"
    )

# ================= SLASH COMMANDS =================

@bot.tree.command(
    name="rank",
    description="Xem rank"
)
async def slash_rank(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    await interaction.response.defer()

    if not member:
        member = interaction.user

    file = await create_rank(member)

    await interaction.followup.send(
        file=file
    )

@bot.tree.command(
    name="toptext",
    description="BXH text"
)
async def slash_toptext(
    interaction: discord.Interaction
):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT user_id, text_xp
        FROM levels
        WHERE guild_id=?
        ORDER BY text_xp DESC
        LIMIT 10
        """, (interaction.guild.id,))

        data = await cursor.fetchall()

    msg = "🏆 TEXT LEADERBOARD\n\n"

    for i, (user_id, xp) in enumerate(data, start=1):

        user = interaction.guild.get_member(user_id)

        if user:

            msg += (
                f"{i}. {user.name} "
                f"- Level {get_level(xp)}\n"
            )

    await interaction.response.send_message(msg)

@bot.tree.command(
    name="topvoice",
    description="BXH voice"
)
async def slash_topvoice(
    interaction: discord.Interaction
):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT user_id, voice_xp
        FROM levels
        WHERE guild_id=?
        ORDER BY voice_xp DESC
        LIMIT 10
        """, (interaction.guild.id,))

        data = await cursor.fetchall()

    msg = "🎤 VOICE LEADERBOARD\n\n"

    for i, (user_id, xp) in enumerate(data, start=1):

        user = interaction.guild.get_member(user_id)

        if user:

            msg += (
                f"{i}. {user.name} "
                f"- Level {get_level(xp)}\n"
            )

    await interaction.response.send_message(msg)

@bot.tree.command(
    name="setrole",
    description="Set role level"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def slash_setrole(
    interaction: discord.Interaction,
    level: int,
    role: discord.Role
):

    async with aiosqlite.connect("levels.db") as db:

        await db.execute("""
        INSERT INTO level_roles(
            guild_id,
            level,
            role_id
        )
        VALUES(?,?,?)
        """, (
            interaction.guild.id,
            level,
            role.id
        ))

        await db.commit()

    await interaction.response.send_message(
        f"✅ Đã set role "
        f"{role.name} cho level {level}"
    )

# ================= READY =================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    await setup_db()

    if not voice_task.is_running():
        voice_task.start()

    try:

        synced = await bot.tree.sync()

        print(
            f"Synced {len(synced)} slash commands"
        )

    except Exception as e:

        print(e)

# ================= RUN =================

bot.run(TOKEN)
