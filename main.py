
import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

# Configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Variables globales
LOG_CHANNEL_ID = None
MAINTENANCE_MODE = False
MAINTENANCE_REASON = ""

@bot.event
async def on_ready():
    print(f'✅ {bot.user} est connecté!')
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commandes synchronisées')
    except Exception as e:
        print(f'❌ Erreur sync: {e}')

# COMMANDES DE MODÉRATION
@bot.tree.command(name="kick", description="Exclure un membre")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Membre exclu", description=f"{member.mention} exclu", color=0xff6b6b)
        embed.add_field(name="Raison", value=reason)
        embed.add_field(name="Par", value=interaction.user.mention)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors de l'exclusion", ephemeral=True)

@bot.tree.command(name="ban", description="Bannir un membre")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Membre banni", description=f"{member.mention} banni", color=0xff0000)
        embed.add_field(name="Raison", value=reason)
        embed.add_field(name="Par", value=interaction.user.mention)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors du ban", ephemeral=True)

@bot.tree.command(name="unban", description="Débannir un utilisateur")
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "Aucune raison"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=reason)
        embed = discord.Embed(title="✅ Utilisateur débanni", description=f"{user.mention} débanni", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors du déban", ephemeral=True)

@bot.tree.command(name="mute", description="Timeout un membre")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "Aucune raison"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    try:
        timeout_until = datetime.now() + timedelta(minutes=minutes)
        await member.timeout(timeout_until, reason=reason)
        embed = discord.Embed(title="🔇 Membre timeout", description=f"{member.mention} timeout {minutes}min", color=0xffa500)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors du timeout", ephemeral=True)

@bot.tree.command(name="unmute", description="Retirer le timeout")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    try:
        await member.timeout(None)
        embed = discord.Embed(title="🔊 Timeout retiré", description=f"{member.mention} peut parler", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur", ephemeral=True)

@bot.tree.command(name="warn", description="Avertir un membre")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    embed = discord.Embed(title="⚠️ Avertissement", description=f"{member.mention} averti", color=0xffff00)
    embed.add_field(name="Raison", value=reason)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear", description="Supprimer des messages")
async def clear(interaction: discord.Interaction, amount: int = 10):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    try:
        await interaction.response.defer()
        deleted = await interaction.channel.purge(limit=min(amount, 100))
        await interaction.followup.send(f"🧹 {len(deleted)} messages supprimés", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur", ephemeral=True)

# COMMANDES SYSTÈME
@bot.tree.command(name="maintenance", description="Mode maintenance ON")
async def maintenance_on(interaction: discord.Interaction, reason: str = "Maintenance"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    global MAINTENANCE_MODE, MAINTENANCE_REASON
    MAINTENANCE_MODE = True
    MAINTENANCE_REASON = reason
    
    embed = discord.Embed(title="🔧 MAINTENANCE ACTIVÉE", description=f"Raison: {reason}", color=0xffa500)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="maintenance_off", description="Mode maintenance OFF")
async def maintenance_off(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    global MAINTENANCE_MODE
    MAINTENANCE_MODE = False
    
    embed = discord.Embed(title="✅ MAINTENANCE DÉSACTIVÉE", description="Serveur opérationnel", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="commands", description="Liste des commandes")
async def commands_list(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Commandes du Bot", color=0x0099ff)
    
    if interaction.user.guild_permissions.administrator:
        embed.add_field(
            name="🔨 Modération", 
            value="/kick /ban /unban /mute /unmute /warn /clear", 
            inline=False
        )
        embed.add_field(
            name="⚙️ Système", 
            value="/maintenance /maintenance_off /commands", 
            inline=False
        )
    else:
        embed.add_field(name="Disponible", value="/commands", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ÉVÉNEMENTS
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Bloquer messages en maintenance (sauf admins)
    if MAINTENANCE_MODE and not message.author.guild_permissions.administrator:
        try:
            await message.delete()
            await message.author.send(f"🔧 Serveur en maintenance: {MAINTENANCE_REASON}")
        except:
            pass
        return
    
    await bot.process_commands(message)

# DÉMARRAGE
if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        print("❌ Token manquant dans les Secrets!")
    else:
        bot.run(token)
