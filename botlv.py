from io import BytesIO
import aiohttp
from PIL import Image, ImageDraw, ImageFont
import discord
from discord import app_commands

# =========================
# RANK COMMAND
# =========================

@bot.tree.command(name="rank", description="Xem rank của bạn")
async def rank(interaction: discord.Interaction, member: discord.Member = None):

    await interaction.response.defer()

    if member is None:
        member = interaction.user

    user_id = str(member.id)

    if user_id not in data:
        data[user_id] = {
            "text_xp": 0,
            "text_level": 1,
            "voice_xp": 0,
            "voice_level": 1
        }

    text_xp = data[user_id]["text_xp"]
    level = data[user_id]["text_level"]

    needed = level * 100

    # =========================
    # TẠO ẢNH
    # =========================

    card = Image.new("RGB", (900, 250), (30, 30, 30))
    draw = ImageDraw.Draw(card)

    # Avatar
    async with aiohttp.ClientSession() as session:
        async with session.get(member.display_avatar.url) as resp:
            avatar_bytes = await resp.read()

    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGB")
    avatar = avatar.resize((180, 180))

    mask = Image.new("L", (180, 180), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, 180, 180), fill=255)

    card.paste(avatar, (30, 35), mask)

    # Font
    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

    # Username
    draw.text(
        (240, 40),
        str(member),
        font=font_big,
        fill=(255, 255, 255)
    )

    # Level
    draw.text(
        (240, 90),
        f"Level: {level}",
        font=font_small,
        fill=(255, 255, 255)
    )

    # XP
    draw.text(
        (240, 130),
        f"XP: {text_xp}/{needed}",
        font=font_small,
        fill=(255, 255, 255)
    )

    # Thanh XP nền
    draw.rounded_rectangle(
        (240, 180, 760, 210),
        radius=20,
        fill=(60, 60, 60)
    )

    # Thanh XP
    bar = int((text_xp / needed) * 520)

    draw.rounded_rectangle(
        (240, 180, 240 + bar, 210),
        radius=20,
        fill=(0, 255, 150)
    )

    # Save ảnh
    buffer = BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)

    file = discord.File(buffer, filename="rank.png")

    await interaction.followup.send(file=file)
