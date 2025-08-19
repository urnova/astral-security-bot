import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
import asyncio
from dotenv import load_dotenv

# --- NOUVEAU: Section pour garder le bot en vie (Flask) ---
# Si vous n'utilisez pas de service comme Replit, vous pouvez supprimer cette section.
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Je suis vivant !"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# --- FIN DE LA SECTION KEEP_ALIVE ---


# --- NOUVEAU: Gestion des données par serveur ---
DATA_FILE = "data.json"
GUILD_DATA = {}

def load_data():
    """Charge les données depuis data.json au démarrage."""
    global GUILD_DATA
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                GUILD_DATA = json.load(f)
            except json.JSONDecodeError:
                GUILD_DATA = {}
    else:
        GUILD_DATA = {}

def save_data():
    """Sauvegarde les données dans data.json."""
    with open(DATA_FILE, 'w') as f:
        json.dump(GUILD_DATA, f, indent=4)

def get_guild_data(guild_id):
    """Récupère les données d'un serveur ou crée une configuration par défaut."""
    guild_id_str = str(guild_id)
    if guild_id_str not in GUILD_DATA:
        GUILD_DATA[guild_id_str] = {
            "LOG_CHANNEL_ID": None,
            "MAINTENANCE_MODE": False,
            "MAINTENANCE_REASON": "",
            "WARNS": {},
            "AUTOMOD_ENABLED": True,
            "RAID_PROTECTION": True,
            "BANNED_WORDS": ["spam", "hack", "scam"]
        }
        save_data()
    return GUILD_DATA[guild_id_str]
# --- FIN DE LA GESTION DES DONNÉES ---


# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Requis pour on_member_join/remove

bot = commands.Bot(command_prefix='!', intents=intents)

# Groupe de commandes 'admin'
admin_group = app_commands.Group(
    name="admin",
    description="Commandes réservées aux administrateateurs",
    default_permissions=discord.Permissions(administrator=True)
)
# LA LIGNE `bot.tree.add_command(admin_group)` A ÉTÉ DÉPLACÉE D'ICI


# Variables globales (pour les données non persistantes)
ANTI_SPAM = {} # Reste en mémoire vive, mais maintenant structuré par serveur
MAX_MENTIONS = 5
MAX_MESSAGES_PER_MINUTE = 10

@bot.event
async def on_ready():
    load_data() # Charger les données au démarrage
    print(f'✅ {bot.user} est connecté!')
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commandes synchronisées')
    except Exception as e:
        print(f'❌ Erreur sync: {e}')

# COMMANDES DE MODÉRATION BASIQUES
@admin_group.command(name="kick", description="Exclure un membre")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Membre exclu", description=f"{member.mention} exclu", color=0xff6b6b)
        embed.add_field(name="Raison", value=reason)
        embed.add_field(name="Par", value=interaction.user.mention)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors de l'exclusion", ephemeral=True)

@admin_group.command(name="ban", description="Bannir un membre")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Membre banni", description=f"{member.mention} banni", color=0xff0000)
        embed.add_field(name="Raison", value=reason)
        embed.add_field(name="Par", value=interaction.user.mention)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors du ban", ephemeral=True)

@admin_group.command(name="unban", description="Débannir un utilisateur")
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "Aucune raison"):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=reason)
        embed = discord.Embed(title="✅ Utilisateur débanni", description=f"{user.mention} débanni", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors du déban", ephemeral=True)

@admin_group.command(name="mute", description="Timeout un membre")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "Aucune raison"):
    try:
        timeout_until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(timeout_until, reason=reason)
        embed = discord.Embed(title="🔇 Membre timeout", description=f"{member.mention} timeout {minutes}min", color=0xffa500)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur lors du timeout", ephemeral=True)

@admin_group.command(name="unmute", description="Retirer le timeout")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None)
        embed = discord.Embed(title="🔊 Timeout retiré", description=f"{member.mention} peut parler", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Erreur", ephemeral=True)

@admin_group.command(name="clear", description="Supprimer des messages")
async def clear(interaction: discord.Interaction, amount: int = 10):
    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=min(amount, 100))
        await interaction.followup.send(f"🧹 {len(deleted)} messages supprimés", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur", ephemeral=True)

# SYSTÈME D'AVERTISSEMENTS
@admin_group.command(name="warn", description="Avertir un membre")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    guild_data = get_guild_data(interaction.guild.id)
    warns = guild_data["WARNS"]
    user_id = str(member.id)

    if user_id not in warns:
        warns[user_id] = []

    warn_data = {
        "reason": reason,
        "moderator": interaction.user.name,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    warns[user_id].append(warn_data)
    save_data() # Sauvegarder

    embed = discord.Embed(title="⚠️ Avertissement", color=0xffff00)
    embed.add_field(name="Membre", value=member.mention)
    embed.add_field(name="Raison", value=reason)
    embed.add_field(name="Total warns", value=len(warns[user_id]))

    await interaction.response.send_message(embed=embed)

    warn_count = len(warns[user_id])
    if warn_count >= 3:
        try:
            await member.ban(reason="3 avertissements atteints")
            await interaction.followup.send(f"🔨 {member.mention} banni automatiquement (3 warns)")
        except:
            pass

@admin_group.command(name="warns", description="Voir les avertissements d'un membre")
async def view_warns(interaction: discord.Interaction, member: discord.Member):
    guild_data = get_guild_data(interaction.guild.id)
    user_id = str(member.id)
    warns = guild_data["WARNS"].get(user_id, [])

    if not warns:
        return await interaction.response.send_message(f"{member.mention} n'a aucun avertissement", ephemeral=True)

    embed = discord.Embed(title=f"⚠️ Avertissements de {member.name}", color=0xffff00)
    for i, warn_data in enumerate(warns, 1):
        embed.add_field(
            name=f"Warn #{i}",
            value=f"**Raison:** {warn_data['reason']}\n**Modérateur:** {warn_data['moderator']}\n**Date:** {warn_data['date']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="unwarn", description="Retirer un avertissement")
async def unwarn(interaction: discord.Interaction, member: discord.Member, warn_number: int):
    guild_data = get_guild_data(interaction.guild.id)
    warns = guild_data["WARNS"]
    user_id = str(member.id)

    if user_id not in warns or not (1 <= warn_number <= len(warns[user_id])):
        return await interaction.response.send_message("❌ Numéro d'avertissement invalide", ephemeral=True)

    removed_warn = warns[user_id].pop(warn_number - 1)
    save_data() # Sauvegarder

    embed = discord.Embed(title="✅ Avertissement retiré", color=0x00ff00)
    embed.add_field(name="Membre", value=member.mention)
    embed.add_field(name="Warn retiré", value=removed_warn['reason'])
    await interaction.response.send_message(embed=embed)

# COMMANDES DE SÉCURITÉ AVANCÉES
@admin_group.command(name="lockdown", description="Verrouiller le serveur")
async def lockdown(interaction: discord.Interaction, reason: str = "Urgence sécuritaire"):
    await interaction.response.send_message("🔒 **INITIALISATION DU VERROUILLAGE...**", ephemeral=True)
    try:
        lockdown_embed = discord.Embed(
            title="🚨 ⚠️ **ALERTE SÉCURITÉ MAXIMALE** ⚠️ 🚨",
            description=f"```diff\n- SERVEUR EN VERROUILLAGE TOTAL\n- ACCÈS COMMUNICATION SUSPENDU\n- SEULS LES ADMINISTRATEURS AUTORISÉS\n```\n\n**📋 RAISON:** `{reason}`\n**🔐 STATUT:** `VERROUILLÉ`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 MODÉRATEUR:** {interaction.user.mention}",
            color=0xff0000
        )
        lockdown_embed.set_image(url="https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif")
        lockdown_embed.set_thumbnail(url="https://media.giphy.com/media/xTiTnHXbRoaZ1B1Mo8/giphy.gif")
        lockdown_embed.add_field(
            name="🛡️ **PROTOCOLE DE SÉCURITÉ ACTIVÉ**",
            value="```yaml\n✅ Communications bloquées\n✅ Permissions révoquées\n✅ Surveillance active\n✅ Mode défensif engagé```",
            inline=False
        )
        lockdown_embed.set_footer(text="🔒 SYSTÈME DE SÉCURITÉ ASTRAL | VERROUILLAGE TOTAL ENGAGÉ")

        locked_channels = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=False)
                locked_channels += 1
            except:
                pass

        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🚨" * 10, embed=lockdown_embed)
            except:
                pass

        await interaction.followup.send(f"✅ **VERROUILLAGE TERMINÉ** - {locked_channels} canaux sécurisés", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur lors du verrouillage", ephemeral=True)

@admin_group.command(name="unlock", description="Déverrouiller le serveur")
async def unlock(interaction: discord.Interaction):
    await interaction.response.send_message("🔓 **INITIALISATION DU DÉVERROUILLAGE...**", ephemeral=True)
    try:
        unlock_embed = discord.Embed(
            title="🎉 ✨ **LIBÉRATION TOTALE** ✨ 🎉",
            description=f"```diff\n+ SERVEUR DÉVERROUILLÉ AVEC SUCCÈS\n+ COMMUNICATIONS RÉTABLIES\n+ ACCÈS TOTAL RESTAURÉ\n```\n\n**🔓 STATUT:** `OPÉRATIONNEL`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 MODÉRATEUR:** {interaction.user.mention}\n**💬 MESSAGE:** `Bienvenue de retour ! Le serveur est maintenant pleinement opérationnel.`",
            color=0x00ff66
        )
        unlock_embed.set_image(url="https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif")
        unlock_embed.set_thumbnail(url="https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif")
        unlock_embed.add_field(name="🎊 **SYSTÈME LIBÉRÉ**", value="```yaml\n✅ Communications rétablies\n✅ Permissions restaurées\n✅ Mode normal activé\n✅ Activité autorisée```", inline=False)
        unlock_embed.add_field(name="🌟 **STATUT DU SERVEUR**", value="```css\n[OPÉRATIONNEL] Toutes les fonctionnalités disponibles\n[SÉCURISÉ] Protection active maintenue\n[STABLE] Système en fonctionnement optimal```", inline=False)
        unlock_embed.set_footer(text="🔓 SYSTÈME DE SÉCURITÉ ASTRAL | ACCÈS TOTAL RESTAURÉ")

        unlocked_channels = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=None)
                unlocked_channels += 1
            except:
                pass
        
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🎉" * 10, embed=unlock_embed)
            except:
                pass

        await interaction.followup.send(f"✅ **DÉVERROUILLAGE TERMINÉ** - {unlocked_channels} canaux libérés", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur lors du déverrouillage", ephemeral=True)

@admin_group.command(name="nuke", description="Supprimer tous les messages du canal")
async def nuke(interaction: discord.Interaction):
    channel = interaction.channel
    try:
        await interaction.response.defer(ephemeral=True)
        
        countdown_embed = discord.Embed(title="💣 ⚠️ **ALERTE DÉTONATION IMMINENTE** ⚠️ 💣", description="Ce canal sera recréé dans 5 secondes...", color=0xff4500)
        countdown_embed.set_image(url="https://media.giphy.com/media/oe33xf3B50fsc/giphy.gif")
        await channel.send(embed=countdown_embed)
        await asyncio.sleep(5)
        
        new_channel = await channel.clone(reason="Nuke command")
        await channel.delete()

        nuke_embed = discord.Embed(title="🌋 💥 **DÉTONATION RÉUSSIE** 💥 🌋", description=f"Ce canal a été purifié par {interaction.user.mention}", color=0xff0000)
        nuke_embed.set_image(url="https://media.giphy.com/media/3oriO0OEd9QIDdllqo/giphy.gif")
        await new_channel.send(embed=nuke_embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors du nuke: {e}", ephemeral=True)

@admin_group.command(name="massban", description="Bannir plusieurs utilisateurs")
async def massban(interaction: discord.Interaction, user_ids: str, reason: str = "Ban de masse"):
    await interaction.response.defer(ephemeral=True)
    ids = user_ids.split()
    banned_count = 0
    for user_id in ids:
        try:
            user = await bot.fetch_user(int(user_id))
            await interaction.guild.ban(user, reason=reason)
            banned_count += 1
        except:
            continue
    embed = discord.Embed(title="🔨 Ban de masse", description=f"{banned_count} utilisateurs bannis", color=0xff0000)
    await interaction.followup.send(embed=embed)

@admin_group.command(name="antiraid", description="Activer/désactiver la protection anti-raid")
async def antiraid(interaction: discord.Interaction, enabled: bool):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["RAID_PROTECTION"] = enabled
    save_data()

    status = "activée" if enabled else "désactivée"
    color = 0x00ff00 if enabled else 0xff0000
    embed = discord.Embed(title="🛡️ Protection Anti-Raid", description=f"Protection {status}", color=color)
    await interaction.response.send_message(embed=embed)

@admin_group.command(name="automod", description="Activer/désactiver l'automodération")
async def automod(interaction: discord.Interaction, enabled: bool):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["AUTOMOD_ENABLED"] = enabled
    save_data()

    status = "activée" if enabled else "désactivée"
    color = 0x00ff00 if enabled else 0xff0000
    embed = discord.Embed(title="🤖 Automodération", description=f"Automod {status}", color=color)
    await interaction.response.send_message(embed=embed)

@admin_group.command(name="addword", description="Ajouter un mot banni")
async def addword(interaction: discord.Interaction, word: str):
    guild_data = get_guild_data(interaction.guild.id)
    banned_words = guild_data["BANNED_WORDS"]
    
    if word.lower() not in banned_words:
        banned_words.append(word.lower())
        save_data()
        embed = discord.Embed(title="🚫 Mot ajouté", description=f"'{word}' ajouté aux mots bannis", color=0xff6b6b)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot est déjà banni", color=0xff0000)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="removeword", description="Retirer un mot banni")
async def removeword(interaction: discord.Interaction, word: str):
    guild_data = get_guild_data(interaction.guild.id)
    banned_words = guild_data["BANNED_WORDS"]

    if word.lower() in banned_words:
        banned_words.remove(word.lower())
        save_data()
        embed = discord.Embed(title="✅ Mot retiré", description=f"'{word}' retiré des mots bannis", color=0x00ff00)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot n'est pas dans la liste", color=0xff0000)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="bannedwords", description="Voir la liste des mots bannis")
async def bannedwords(interaction: discord.Interaction):
    guild_data = get_guild_data(interaction.guild.id)
    banned_words = guild_data["BANNED_WORDS"]

    if not banned_words:
        return await interaction.response.send_message("Aucun mot banni", ephemeral=True)

    embed = discord.Embed(title="🚫 Mots bannis", description="\n".join(banned_words), color=0xff6b6b)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# COMMANDES SYSTÈME
@admin_group.command(name="maintenance", description="Mode maintenance ON")
async def maintenance_on(interaction: discord.Interaction, reason: str = "Maintenance"):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["MAINTENANCE_MODE"] = True
    guild_data["MAINTENANCE_REASON"] = reason
    save_data()

    await interaction.response.send_message("🔧 **INITIALISATION DU MODE MAINTENANCE...**", ephemeral=True)
    try:
        maintenance_embed = discord.Embed(title="🚧 ⚠️ **MAINTENANCE EN COURS** ⚠️ 🚧", description=f"```diff\n- SERVEUR EN MAINTENANCE TECHNIQUE\n- ACCÈS UTILISATEUR SUSPENDU\n```\n\n**🔧 RAISON:** `{reason}`", color=0xffa500)
        maintenance_embed.set_image(url="https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif")

        for channel in interaction.guild.text_channels:
            try:
                await channel.send(embed=maintenance_embed)
            except:
                pass
        
        await interaction.followup.send("✅ **MODE MAINTENANCE ACTIVÉ**", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur lors de l'activation de la maintenance", ephemeral=True)

@admin_group.command(name="maintenance_off", description="Mode maintenance OFF")
async def maintenance_off(interaction: discord.Interaction):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["MAINTENANCE_MODE"] = False
    save_data()

    await interaction.response.send_message("✅ **FINALISATION DE LA MAINTENANCE...**", ephemeral=True)
    try:
        end_maintenance_embed = discord.Embed(title="🎉 ✨ **MAINTENANCE TERMINÉE** ✨ 🎉", description="```diff\n+ SERVEUR PLEINEMENT OPÉRATIONNEL\n+ COMMUNICATIONS RÉTABLIES\n```", color=0x00ff66)
        end_maintenance_embed.set_image(url="https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif")
        
        for channel in interaction.guild.text_channels:
            try:
                await channel.send(embed=end_maintenance_embed)
            except:
                pass
        
        await interaction.followup.send("✅ **MAINTENANCE TERMINÉE**", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur lors de la fin de la maintenance", ephemeral=True)

@admin_group.command(name="setlogchannel", description="Définir le canal de logs")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["LOG_CHANNEL_ID"] = channel.id
    save_data()

    embed = discord.Embed(title="📝 Canal de logs défini", description=f"Les logs seront désormais envoyés dans {channel.mention}", color=0x0099ff)
    await interaction.response.send_message(embed=embed)

async def log_action(guild: discord.Guild, embed: discord.Embed):
    """Fonction pour envoyer un log dans le canal configuré."""
    guild_data = get_guild_data(guild.id)
    log_channel_id = guild_data.get("LOG_CHANNEL_ID")
    if log_channel_id:
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                print(f"Permissions manquantes pour envoyer des logs dans le canal {log_channel_id} du serveur {guild.name}")

@admin_group.command(name="say", description="Faire parler le bot")
async def say(interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel
    try:
        await target_channel.send(message)
        await interaction.response.send_message(f"✅ Message envoyé dans {target_channel.mention}", ephemeral=True)

        log_embed = discord.Embed(title="📤 Message envoyé par un admin", color=0x0099ff, timestamp=datetime.now())
        log_embed.add_field(name="Contenu", value=message, inline=False)
        log_embed.add_field(name="Administrateur", value=interaction.user.mention)
        log_embed.add_field(name="Canal", value=target_channel.mention)
        await log_action(interaction.guild, log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur: {e}", ephemeral=True)

@admin_group.command(name="embed", description="Envoyer un message embed via le bot")
async def send_embed(interaction: discord.Interaction, title: str, description: str, channel: discord.TextChannel = None, color: str = "0x0099ff"):
    target_channel = channel or interaction.channel
    try:
        embed_color = int(color.replace("#", ""), 16)
    except ValueError:
        return await interaction.response.send_message("❌ Format de couleur invalide. Utilisez le format hexadécimal (ex: `0099ff`).", ephemeral=True)

    embed = discord.Embed(title=title, description=description, color=embed_color, timestamp=datetime.now())
    embed.set_footer(text=f"Message de {interaction.guild.name}")
    await target_channel.send(embed=embed)
    
    await interaction.response.send_message(f"✅ Embed envoyé dans {target_channel.mention}", ephemeral=True)

    log_embed = discord.Embed(title="📤 Embed envoyé par un admin", color=0x0099ff, timestamp=datetime.now())
    log_embed.add_field(name="Titre", value=title, inline=False)
    log_embed.add_field(name="Administrateur", value=interaction.user.mention)
    await log_action(interaction.guild, log_embed)

@admin_group.command(name="announce", description="Envoyer une annonce officielle")
async def announce(interaction: discord.Interaction, title: str, message: str, channel: discord.TextChannel = None, ping_everyone: bool = False):
    target_channel = channel or interaction.channel
    try:
        announce_embed = discord.Embed(title=f"📢 {title}", description=message, color=0xffd700, timestamp=datetime.now())
        announce_embed.set_footer(text=f"Annonce de {interaction.guild.name}")
        if interaction.guild.icon:
            announce_embed.set_author(name="ANNONCE OFFICIELLE", icon_url=interaction.guild.icon.url)
        
        content = "@everyone" if ping_everyone else ""
        await target_channel.send(content=content, embed=announce_embed)

        await interaction.response.send_message(f"✅ Annonce envoyée dans {target_channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur: {e}", ephemeral=True)

@admin_group.command(name="dm", description="Envoyer un MP à un utilisateur via le bot")
async def send_dm(interaction: discord.Interaction, member: discord.Member, message: str):
    try:
        dm_embed = discord.Embed(title=f"📨 Message de {interaction.guild.name}", description=message, color=0x0099ff, timestamp=datetime.now())
        if interaction.guild.icon:
            dm_embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await member.send(embed=dm_embed)

        await interaction.response.send_message(f"✅ MP envoyé à {member.mention}", ephemeral=True)

        log_embed = discord.Embed(title="📨 MP envoyé par un admin", color=0x0099ff, timestamp=datetime.now())
        log_embed.add_field(name="Destinataire", value=member.mention)
        log_embed.add_field(name="Administrateur", value=interaction.user.mention)
        await log_action(interaction.guild, log_embed)
    except discord.Forbidden:
        await interaction.response.send_message(f"❌ Impossible d'envoyer un MP à {member.mention} (ses MPs sont probablement fermés).", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur: {e}", ephemeral=True)

# COMMANDES GÉNÉRALES
@bot.tree.command(name="serverinfo", description="Informations du serveur")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 Informations sur {guild.name}", color=0x0099ff)
    embed.add_field(name="Membres", value=guild.member_count)
    embed.add_field(name="Canaux", value=len(guild.channels))
    embed.add_field(name="Rôles", value=len(guild.roles))
    embed.add_field(name="Créé le", value=guild.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Propriétaire", value=guild.owner.mention if guild.owner else "Inconnu")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Informations d'un utilisateur")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"👤 Informations sur {member.display_name}", color=member.color)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="A rejoint le serveur le", value=member.joined_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Compte créé le", value=member.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Nombre de rôles", value=len(member.roles) - 1)
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    await interaction.response.send_message(embed=embed)
    
@bot.tree.command(name="commands", description="Liste détaillée des commandes")
async def commands_list(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 Liste des commandes", color=0x0099ff)
    if interaction.user.guild_permissions.administrator:
        embed.add_field(name="🔨 Modération", value="`/admin kick`, `/admin ban`, `/admin unban`, `/admin mute`, `/admin unmute`, `/admin clear`", inline=False)
        embed.add_field(name="⚠️ Avertissements", value="`/admin warn`, `/admin warns`, `/admin unwarn`", inline=False)
        embed.add_field(name="🛡️ Sécurité", value="`/admin lockdown`, `/admin unlock`, `/admin nuke`, `/admin massban`", inline=False)
        embed.add_field(name="🤖 Automodération", value="`/admin antiraid`, `/admin automod`, `/admin addword`, `/admin removeword`, `/admin bannedwords`", inline=False)
        embed.add_field(name="📤 Communication", value="`/admin say`, `/admin embed`, `/admin announce`, `/admin dm`", inline=False)
        embed.add_field(name="⚙️ Système", value="`/admin maintenance`, `/admin maintenance_off`, `/admin setlogchannel`", inline=False)
    
    embed.add_field(name="🌐 Commandes Générales", value="`/commands`, `/serverinfo`, `/userinfo`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# --- CORRECTION APPLIQUÉE ICI ---
# On ajoute le groupe de commandes au bot APRÈS avoir défini toutes les commandes du groupe.
bot.tree.add_command(admin_group)


# ÉVÉNEMENTS DE SÉCURITÉ
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_data = get_guild_data(message.guild.id)

    if guild_data["MAINTENANCE_MODE"] and not message.author.guild_permissions.administrator:
        try:
            await message.delete()
            await message.author.send(f"🔧 Le serveur est actuellement en maintenance pour la raison suivante : {guild_data['MAINTENANCE_REASON']}")
        except: pass
        return

    if guild_data["AUTOMOD_ENABLED"] and not message.author.guild_permissions.administrator:
        content_lower = message.content.lower()
        for word in guild_data["BANNED_WORDS"]:
            if word in content_lower:
                await message.delete()
                try: await message.author.send("⚠️ Votre message a été supprimé car il contenait un mot interdit.")
                except: pass
                return

        guild_id = message.guild.id
        user_id = message.author.id
        now = datetime.now()

        if guild_id not in ANTI_SPAM: ANTI_SPAM[guild_id] = {}
        if user_id not in ANTI_SPAM[guild_id]: ANTI_SPAM[guild_id][user_id] = []
        
        ANTI_SPAM[guild_id][user_id] = [t for t in ANTI_SPAM[guild_id][user_id] if (now - t).seconds < 60]
        ANTI_SPAM[guild_id][user_id].append(now)

        if len(ANTI_SPAM[guild_id][user_id]) > MAX_MESSAGES_PER_MINUTE:
            try:
                await message.author.timeout(discord.utils.utcnow() + timedelta(minutes=5), reason="Spam détecté")
                await message.channel.send(f"🔇 {message.author.mention} a été rendu muet pendant 5 minutes pour spam.")
            except: pass

        if len(message.mentions) > MAX_MENTIONS:
            await message.delete()
            try: await message.author.timeout(discord.utils.utcnow() + timedelta(minutes=2), reason="Mentions excessives")
            except: pass

@bot.event
async def on_member_join(member):
    guild_data = get_guild_data(member.guild.id)
    if guild_data["RAID_PROTECTION"]:
        account_age = discord.utils.utcnow() - member.created_at
        if account_age.days < 7:
            try:
                await member.ban(reason="Protection anti-raid: compte trop récent")
                log_embed = discord.Embed(title="🛡️ Anti-raid activé", description=f"{member.mention} a été banni car son compte a moins de 7 jours.", color=0xff0000)
                await log_action(member.guild, log_embed)
            except: pass

@bot.event
async def on_member_remove(member):
    log_embed = discord.Embed(title="👋 Un membre est parti", description=f"**{member.name}** a quitté le serveur.", color=0xffa500, timestamp=datetime.now())
    await log_action(member.guild, log_embed)


# DÉMARRAGE
if __name__ == "__main__":
    # Initialisation du système de logs
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Chargement des variables d'environnement
    load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN")
    
    if not token:
        logging.critical("❌ Token manquant! Définissez la variable DISCORD_BOT_TOKEN dans .env")
        sys.exit(1)  # Quitte avec code d'erreur
    
    # Configuration des dossiers
    os.makedirs('configs', exist_ok=True)
    
    # Gestion des erreurs spécifiques
    try:
        logging.info("🚀 Démarrage du bot...")
        bot.run(token)
    except discord.errors.LoginFailure:
        logging.critical("🔑 Token invalide! Vérifiez votre token Discord")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("🛑 Arrêt manuel du bot")
        sys.exit(0)
    except Exception as e:
        logging.error(f"💥 Erreur inattendue: {str(e)}")
        sys.exit(1)
