import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import random
import os
import asyncio
from easy_pil import Editor, Font, load_image_async

TOKEN = os.getenv("TOKEN")

LEVEL_UP_CHANNEL_ID = 1478478635491918027

intents = discord.Intents.all()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="f",
    intents=intents
)

cooldown = {}

# ================= DATABASE =================

async def setup_db():

    async with aiosqlite.connect("levels.db") as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS levels(
            guild_id INTEGER,
            user_id INTEGER,
            text_xp INTEGER DEFAULT 0,
            text_level INTEGER DEFAULT 0,
            voice_xp INTEGER DEFAULT 0,
            voice_level INTEGER DEFAULT 0,
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

# ================= XP =================

def xp_needed(level):
    return 100 * (level ** 2) + 100

def calc_level(xp):

    level = 0

    while xp >= xp_needed(level):

        xp -= xp_needed(level)
        level += 1

    return level

# ================= READY =================

@bot.event
async def on_ready():

    await setup_db()

    voice_xp_task.start()

    try:

        synced = await bot.tree.sync()

        print(f"Synced {len(synced)} slash commands")

    except Exception as e:
        print(e)

    print(f"Logged in as {bot.user}")

# ================= TEXT XP =================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return

    user_id = message.author.id
    guild_id = message.guild.id

    # cooldown chống spam
    if user_id in cooldown:

        if cooldown[user_id] > asyncio.get_event_loop().time():

            await bot.process_commands(message)
            return

    cooldown[user_id] = asyncio.get_event_loop().time() + 10

    xp_gain = random.randint(15, 25)

    async with aiosqlite.connect("levels.db") as db:

        await db.execute("""
        INSERT OR IGNORE INTO levels
        (guild_id, user_id, text_xp, text_level, voice_xp, voice_level)
        VALUES (?, ?, 0, 0, 0, 0)
        """, (guild_id, user_id))

        cursor = await db.execute("""
        SELECT text_xp, text_level
        FROM levels
        WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))

        data = await cursor.fetchone()

        old_xp = data[0]
        old_level = data[1]

        new_xp = old_xp + xp_gain
        new_level = calc_level(new_xp)

        await db.execute("""
        UPDATE levels
        SET text_xp = ?, text_level = ?
        WHERE guild_id = ? AND user_id = ?
        """, (new_xp, new_level, guild_id, user_id))

        await db.commit()

    # level up
    if new_level > old_level:

        channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)

        if channel:

            await channel.send(
                f"🎉 {message.author.mention} đã lên text level **{new_level}**!"
            )

        # role reward
        async with aiosqlite.connect("levels.db") as db:

            cursor = await db.execute("""
            SELECT role_id
            FROM level_roles
            WHERE guild_id = ? AND level = ?
            """, (guild_id, new_level))

            role_data = await cursor.fetchone()

            if role_data:

                role = message.guild.get_role(role_data[0])

                if role:

                    try:
                        await message.author.add_roles(role)

                    except:
                        pass

    await bot.process_commands(message)

# ================= VOICE XP =================

@tasks.loop(minutes=1)
async def voice_xp_task():

    for guild in bot.guilds:

        for vc in guild.voice_channels:

            for member in vc.members:

                if member.bot:
                    continue

                async with aiosqlite.connect("levels.db") as db:

                    await db.execute("""
                    INSERT OR IGNORE INTO levels
                    (guild_id, user_id, text_xp, text_level, voice_xp, voice_level)
                    VALUES (?, ?, 0, 0, 0, 0)
                    """, (guild.id, member.id))

                    cursor = await db.execute("""
                    SELECT voice_xp, voice_level
                    FROM levels
                    WHERE guild_id = ? AND user_id = ?
                    """, (guild.id, member.id))

                    data = await cursor.fetchone()

                    old_xp = data[0]
                    old_level = data[1]

                    gain = random.randint(10, 18)

                    new_xp = old_xp + gain
                    new_level = calc_level(new_xp)

                    await db.execute("""
                    UPDATE levels
                    SET voice_xp = ?, voice_level = ?
                    WHERE guild_id = ? AND user_id = ?
                    """, (new_xp, new_level, guild.id, member.id))

                    await db.commit()

                if new_level > old_level:

                    channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)

                    if channel:

                        await channel.send(
                            f"🎤 {member.mention} đã lên voice level **{new_level}**!"
                        )

# ================= RANK CARD =================

async def create_rank_card(member, data):

    text_level = data[1]
    voice_level = data[3]

    background = Editor(
        "https://i.imgur.com/4M34hi2.png"
    )

    profile = await load_image_async(
        str(member.display_avatar.url)
    )

    profile = Editor(profile).resize((150, 150)).circle_image()

    background.paste(profile, (40, 40))

    font = Font.poppins(size=40)
    small_font = Font.poppins(size=28)

    background.text(
        (220, 50),
        member.name,
        color="white",
        font=font
    )

    background.text(
        (220, 120),
        f"Text Level: {text_level}",
        color="white",
        font=small_font
    )

    background.text(
        (220, 170),
        f"Voice Level: {voice_level}",
        color="white",
        font=small_font
    )

    file = discord.File(
        fp=background.image_bytes,
        filename="rank.png"
    )

    return file

# ================= PREFIX RANK =================

@bot.command()
async def rank(ctx, member: discord.Member = None):

    if not member:
        member = ctx.author

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT text_xp, text_level, voice_xp, voice_level
        FROM levels
        WHERE guild_id = ? AND user_id = ?
        """, (ctx.guild.id, member.id))

        data = await cursor.fetchone()

    if not data:
        return await ctx.send("Chưa có dữ liệu.")

    file = await create_rank_card(member, data)

    await ctx.send(file=file)

# ================= SLASH RANK =================

@bot.tree.command(
    name="rank",
    description="Xem rank"
)
async def slash_rank(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    if not member:
        member = interaction.user

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT text_xp, text_level, voice_xp, voice_level
        FROM levels
        WHERE guild_id = ? AND user_id = ?
        """, (interaction.guild.id, member.id))

        data = await cursor.fetchone()

    if not data:
        return await interaction.response.send_message(
            "Chưa có dữ liệu."
        )

    file = await create_rank_card(member, data)

    await interaction.response.send_message(file=file)

# ================= TOP =================

@bot.command()
async def top(ctx):

    async with aiosqlite.connect("levels.db") as db:

        cursor = await db.execute("""
        SELECT user_id, text_level, voice_level
        FROM levels
        WHERE guild_id = ?
        ORDER BY text_level DESC
        LIMIT 10
        """, (ctx.guild.id,))

        data = await cursor.fetchall()

    msg = "🏆 Leaderboard\n\n"

    for i, row in enumerate(data, start=1):

        member = ctx.guild.get_member(row[0])

        if member:

            msg += (
                f"{i}. {member.name} | "
                f"Text Lv: {row[1]} | "
                f"Voice Lv: {row[2]}\n"
            )

    await ctx.send(msg)

# ================= SETROLE =================

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
        VALUES (?, ?, ?)
        """, (
            ctx.guild.id,
            level,
            role.id
        ))

        await db.commit()

    await ctx.send(
        f"Đã set {role.mention} cho level {level}"
    )

# ================= RUN =================

bot.run(TOKEN)
