import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import random
import asyncio
import os
from easy_pil import Editor, Font, load_image_async
from io import BytesIO

TOKEN = os.getenv("TOKEN")

# ID kênh thông báo level
LEVEL_UP_CHANNEL_ID = 1478478635491918027

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="f",
    intents=intents
)

tree = bot.tree

# ================= DATABASE =================

db = sqlite3.connect("levels.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS levels (
    guild_id INTEGER,
    user_id INTEGER,
    text_xp INTEGER DEFAULT 0,
    text_level INTEGER DEFAULT 0,
    voice_xp INTEGER DEFAULT 0,
    voice_level INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS level_roles (
    guild_id INTEGER,
    level INTEGER,
    role_id INTEGER,
    PRIMARY KEY (guild_id, level)
)
""")

db.commit()

# ================= SYSTEM =================

cooldown = {}

def xp_needed(level):
    return 5 * (level ** 2) + 50 * level + 100

def get_data(guild_id, user_id):

    cursor.execute(
        "SELECT * FROM levels WHERE guild_id=? AND user_id=?",
        (guild_id, user_id)
    )

    data = cursor.fetchone()

    if data is None:

        cursor.execute(
            "INSERT INTO levels VALUES (?, ?, 0, 0, 0, 0)",
            (guild_id, user_id)
        )

        db.commit()

        return (guild_id, user_id, 0, 0, 0, 0)

    return data

# ================= LEVEL ROLE =================

async def check_level_role(member, level):

    cursor.execute(
        "SELECT role_id FROM level_roles WHERE guild_id=? AND level=?",
        (member.guild.id, level)
    )

    data = cursor.fetchone()

    if data:

        role = member.guild.get_role(data[0])

        if role:

            try:
                await member.add_roles(role)
            except:
                pass

# ================= LEVEL UP MESSAGE =================

async def send_level_message(member, level, level_type="text"):

    channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)

    if channel is None:
        return

    if level_type == "text":

        await channel.send(
            f"🎉 {member.mention} đã lên text level {level}!"
        )

    else:

        await channel.send(
            f"🎧 {member.mention} đã lên voice level {level}!"
        )

# ================= TEXT LEVEL =================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return

    key = f"{message.guild.id}-{message.author.id}"

    if key in cooldown:
        return

    cooldown[key] = True

    async def remove_cooldown():
        await asyncio.sleep(10)
        cooldown.pop(key, None)

    asyncio.create_task(remove_cooldown())

    data = get_data(
        message.guild.id,
        message.author.id
    )

    xp = data[2]
    level = data[3]

    gain = random.randint(10, 20)

    xp += gain

    need = xp_needed(level)

    if xp >= need:

        level += 1

        await send_level_message(
            message.author,
            level,
            "text"
        )

        await check_level_role(
            message.author,
            level
        )

    cursor.execute("""
    UPDATE levels
    SET text_xp=?, text_level=?
    WHERE guild_id=? AND user_id=?
    """, (
        xp,
        level,
        message.guild.id,
        message.author.id
    ))

    db.commit()

    await bot.process_commands(message)

# ================= VOICE LEVEL =================

@tasks.loop(minutes=1)
async def voice_task():

    for guild in bot.guilds:

        for vc in guild.voice_channels:

            for member in vc.members:

                if member.bot:
                    continue

                data = get_data(
                    guild.id,
                    member.id
                )

                xp = data[4]
                level = data[5]

                xp += 15

                need = xp_needed(level)

                if xp >= need:

                    level += 1

                    await send_level_message(
                        member,
                        level,
                        "voice"
                    )

                    await check_level_role(
                        member,
                        level
                    )

                cursor.execute("""
                UPDATE levels
                SET voice_xp=?, voice_level=?
                WHERE guild_id=? AND user_id=?
                """, (
                    xp,
                    level,
                    guild.id,
                    member.id
                ))

    db.commit()

# ================= RANK =================

@tree.command(
    name="rank",
    description="Xem rank"
)
async def rank(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    await interaction.response.defer()

    if member is None:
        member = interaction.user

    data = get_data(
        interaction.guild.id,
        member.id
    )

    xp = data[2]
    level = data[3]

    need = xp_needed(level)

    percentage = int((xp / need) * 100)

    # NỀN KHÔNG CẦN ẢNH
    background = Editor(
        (800, 300),
        color="#2B2D31"
    )

    # AVATAR
    profile = await load_image_async(
        str(member.display_avatar.url)
    )

    profile = Editor(profile).resize(
        (150, 150)
    ).circle_image()

    background.paste(profile, (50, 75))

    # THANH XP
    background.rectangle(
        (250, 180),
        width=500,
        height=40,
        fill="#23272A",
        radius=20
    )

    background.bar(
        (250, 180),
        max_width=500,
        height=40,
        percentage=percentage,
        fill="#5865F2",
        radius=20
    )

    poppins = Font.poppins(size=40)

    # TEXT
    background.text(
        (250, 70),
        member.name,
        font=poppins,
        color="white"
    )

    background.text(
        (250, 120),
        f"Level: {level}",
        font=poppins,
        color="white"
    )

    background.text(
        (550, 120),
        f"{xp}/{need} XP",
        font=poppins,
        color="white"
    )

    file = discord.File(
        fp=BytesIO(background.image_bytes),
        filename="rank.png"
    )

    await interaction.followup.send(
        file=file
    )

# ================= LEADERBOARD =================

@tree.command(
    name="leaderboard",
    description="BXH level"
)
async def leaderboard(interaction: discord.Interaction):

    cursor.execute("""
    SELECT user_id, text_level, text_xp
    FROM levels
    WHERE guild_id=?
    ORDER BY text_level DESC, text_xp DESC
    LIMIT 10
    """, (interaction.guild.id,))

    data = cursor.fetchall()

    embed = discord.Embed(
        title="🏆 Leaderboard",
        color=discord.Color.blurple()
    )

    for i, user_data in enumerate(data, start=1):

        member = interaction.guild.get_member(
            user_data[0]
        )

        if member:

            embed.add_field(
                name=f"#{i} - {member}",
                value=f"Level: {user_data[1]} | XP: {user_data[2]}",
                inline=False
            )

    await interaction.response.send_message(
        embed=embed
    )

# ================= SET ROLE =================

@tree.command(
    name="setrole",
    description="Set role level"
)
@app_commands.describe(
    level="Level cần nhận role",
    role="Role nhận"
)
async def setrole(
    interaction: discord.Interaction,
    level: int,
    role: discord.Role
):

    if not interaction.user.guild_permissions.administrator:

        return await interaction.response.send_message(
            "❌ Bạn không có quyền.",
            ephemeral=True
        )

    cursor.execute("""
    INSERT OR REPLACE INTO level_roles
    VALUES (?, ?, ?)
    """, (
        interaction.guild.id,
        level,
        role.id
    ))

    db.commit()

    await interaction.response.send_message(
        f"✅ Level {level} sẽ nhận {role.mention}"
    )

# ================= READY =================

@bot.event
async def on_ready():

    await tree.sync()

    voice_task.start()

    print(f"Logged in as {bot.user}")

# ================= START =================

bot.run(TOKEN)
