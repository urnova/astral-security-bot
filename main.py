import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
import asyncio
import logging
from dotenv import load_dotenv

# --- Gestion des données par serveur avec data.json ---
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
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Variables globales non-persistantes
ANTI_SPAM = {}
MAX_MENTIONS = 5
MAX_MESSAGES_PER_MINUTE = 10

@bot.event
async def on_ready():
    load_data()
    print(f'✅ {bot.user} est connecté!')
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commandes synchronisées')
    except Exception as e:
        print(f'❌ Erreur de synchronisation: {e}')

# ---------------------------------------------------------------------------
# --------------------- COMMANDES DE MODÉRATION DE BASE ---------------------
# ---------------------------------------------------------------------------

@bot.tree.command(name="kick", description="Exclure un membre du serveur.")
@app_commands.checks.has_permissions(administrator=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison fournie"):
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Membre Exclu", description=f"{member.mention} a été exclu avec succès.", color=0xff6b6b)
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'exclusion : {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Bannir un membre définitivement.")
@app_commands.checks.has_permissions(administrator=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison fournie"):
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Membre Banni", description=f"{member.mention} a été banni avec succès.", color=0xff0000)
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.add_field(name="Modérateur", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors du bannissement : {e}", ephemeral=True)

@bot.tree.command(name="unban", description="Débannir un utilisateur via son ID.")
@app_commands.checks.has_permissions(administrator=True)
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "Aucune raison fournie"):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=reason)
        embed = discord.Embed(title="✅ Utilisateur Débanni", description=f"{user.mention} a été débanni.", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors du déban. L'ID est-il correct ? {e}", ephemeral=True)

@bot.tree.command(name="mute", description="Rendre un membre muet temporairement.")
@app_commands.checks.has_permissions(administrator=True)
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "Aucune raison fournie"):
    try:
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        embed = discord.Embed(title="🔇 Membre Mute", description=f"{member.mention} est maintenant muet pour {minutes} minute(s).", color=0xffa500)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors du mute : {e}", ephemeral=True)

@bot.tree.command(name="unmute", description="Retirer le mute d'un membre.")
@app_commands.checks.has_permissions(administrator=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None)
        embed = discord.Embed(title="🔊 Mute Retiré", description=f"{member.mention} peut de nouveau parler.", color=0x00ff00)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

@bot.tree.command(name="clear", description="Supprimer un nombre de messages dans le canal.")
@app_commands.checks.has_permissions(administrator=True)
async def clear(interaction: discord.Interaction, amount: int):
    if amount <= 0 or amount > 100:
        return await interaction.response.send_message("Veuillez choisir un nombre entre 1 et 100.", ephemeral=True)
    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 {len(deleted)} messages ont été supprimés avec succès.")
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur lors de la suppression : {e}")

# ---------------------------------------------------------------------------
# ------------------------ SYSTÈME D'AVERTISSEMENTS ------------------------
# ---------------------------------------------------------------------------

@bot.tree.command(name="warn", description="Avertir un membre.")
@app_commands.checks.has_permissions(administrator=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison fournie"):
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
    save_data()

    embed = discord.Embed(title="⚠️ Avertissement Donné", color=0xffff00)
    embed.add_field(name="Membre", value=member.mention)
    embed.add_field(name="Raison", value=reason)
    embed.add_field(name="Nombre total d'avertissements", value=len(warns[user_id]))
    await interaction.response.send_message(embed=embed)

    if len(warns[user_id]) >= 3:
        try:
            await member.ban(reason="3 avertissements atteints")
            await interaction.followup.send(f"🔨 {member.mention} a été banni automatiquement pour avoir atteint 3 avertissements.")
        except:
            pass

@bot.tree.command(name="warns", description="Voir les avertissements d'un membre.")
@app_commands.checks.has_permissions(administrator=True)
async def view_warns(interaction: discord.Interaction, member: discord.Member):
    guild_data = get_guild_data(interaction.guild.id)
    warns_list = guild_data["WARNS"].get(str(member.id), [])

    if not warns_list:
        return await interaction.response.send_message(f"{member.mention} n'a aucun avertissement.", ephemeral=True)

    embed = discord.Embed(title=f"⚠️ Avertissements de {member.name}", color=0xffff00)
    for i, warn in enumerate(warns_list, 1):
        embed.add_field(
            name=f"Avertissement #{i}",
            value=f"**Raison:** {warn['reason']}\n**Modérateur:** {warn['moderator']}\n**Date:** {warn['date']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="unwarn", description="Retirer un avertissement d'un membre.")
@app_commands.checks.has_permissions(administrator=True)
async def unwarn(interaction: discord.Interaction, member: discord.Member, warn_number: int):
    guild_data = get_guild_data(interaction.guild.id)
    warns_list = guild_data["WARNS"].get(str(member.id), [])

    if not (1 <= warn_number <= len(warns_list)):
        return await interaction.response.send_message("❌ Numéro d'avertissement invalide.", ephemeral=True)

    removed = warns_list.pop(warn_number - 1)
    save_data()
    
    embed = discord.Embed(title="✅ Avertissement Retiré", description=f"L'avertissement pour `{removed['reason']}` a été retiré de {member.mention}.", color=0x00ff00)
    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------------------------
# ----------------------- COMMANDES DE SÉCURITÉ AVANCÉES ----------------------
# ---------------------------------------------------------------------------

@bot.tree.command(name="lockdown", description="Verrouiller tous les canaux du serveur.")
@app_commands.checks.has_permissions(administrator=True)
async def lockdown(interaction: discord.Interaction, reason: str = "Urgence sécuritaire"):
    await interaction.response.send_message("🔒 **Initialisation du protocole de verrouillage...**", ephemeral=True)
    
    embed = discord.Embed(
        title="🚨 ⚠️ ALERTE SÉCURITÉ MAXIMALE ⚠️ 🚨",
        description=f"```diff\n- SERVEUR EN VERROUILLAGE TOTAL\n- COMMUNICATIONS SUSPENDUES\n```\n**📋 RAISON:** `{reason}`\n**👤 ACTIVÉ PAR:** {interaction.user.mention}",
        color=0xff0000
    )
    embed.set_image(url="https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif")
    embed.set_thumbnail(url="https://i.gifer.com/origin/f1/f1258284b5c7f82e11a39d80a527034c_w200.gif")
    embed.set_footer(text="Système de Sécurité | Verrouillage Total Engagé")

    locked_count = 0
    for channel in interaction.guild.text_channels:
        try:
            await channel.set_permissions(interaction.guild.default_role, send_messages=False)
            await channel.send(embed=embed)
            locked_count += 1
        except:
            continue
            
    await interaction.followup.send(f"✅ **Verrouillage terminé.** {locked_count} canaux ont été sécurisés.", ephemeral=True)

@bot.tree.command(name="unlock", description="Déverrouiller tous les canaux du serveur.")
@app_commands.checks.has_permissions(administrator=True)
async def unlock(interaction: discord.Interaction):
    await interaction.response.send_message("🔓 **Initialisation du déverrouillage...**", ephemeral=True)

    embed = discord.Embed(
        title="🎉 ✨ LIBÉRATION TOTALE ✨ 🎉",
        description=f"```diff\n+ SERVEUR DÉVERROUILLÉ\n+ COMMUNICATIONS RÉTABLIES\n```\n**👤 DÉSACTIVÉ PAR:** {interaction.user.mention}",
        color=0x00ff66
    )
    embed.set_image(url="https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif")
    embed.set_footer(text="Système de Sécurité | Accès Total Restauré")

    unlocked_count = 0
    for channel in interaction.guild.text_channels:
        try:
            await channel.set_permissions(interaction.guild.default_role, send_messages=None)
            await channel.send(embed=embed)
            unlocked_count += 1
        except:
            continue
            
    await interaction.followup.send(f"✅ **Déverrouillage terminé.** {unlocked_count} canaux ont été libérés.", ephemeral=True)

@bot.tree.command(name="nuke", description="Recrée le canal pour effacer tous les messages.")
@app_commands.checks.has_permissions(administrator=True)
async def nuke(interaction: discord.Interaction):
    channel = interaction.channel
    
    await interaction.response.send_message("💥 **Préparation de la détonation...**", ephemeral=True)

    countdown_embed = discord.Embed(
        title="💣 ⚠️ DÉTONATION IMMINENTE ⚠️ 💣",
        description="Ce canal sera entièrement purifié dans 5 secondes...",
        color=0xff4500
    )
    countdown_embed.set_image(url="https://media.giphy.com/media/oe33xf3B50fsc/giphy.gif")
    await channel.send(embed=countdown_embed)
    await asyncio.sleep(5)

    try:
        new_channel = await channel.clone(reason=f"Nuke demandé par {interaction.user.name}")
        await channel.delete()

        nuke_embed = discord.Embed(
            title="🌋 💥 DÉTONATION RÉUSSIE 💥 🌋",
            description=f"Ce canal a été purifié par {interaction.user.mention}.",
            color=0xff0000
        )
        nuke_embed.set_image(url="https://media.giphy.com/media/3oriO0OEd9QIDdllqo/giphy.gif")
        await new_channel.send(embed=nuke_embed)
    except discord.Forbidden:
        await interaction.followup.send("❌ Permission manquante pour effectuer cette action.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Une erreur est survenue: {e}", ephemeral=True)

# ---------------------------------------------------------------------------
# ----------------------- AUTOMODÉRATION ET SYSTÈME ------------------------
# ---------------------------------------------------------------------------

@bot.tree.command(name="maintenance", description="Active le mode maintenance sur le serveur.")
@app_commands.checks.has_permissions(administrator=True)
async def maintenance(interaction: discord.Interaction, reason: str):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["MAINTENANCE_MODE"] = True
    guild_data["MAINTENANCE_REASON"] = reason
    save_data()

    await interaction.response.send_message("🔧 **Mode maintenance activé.**", ephemeral=True)
    
    embed = discord.Embed(
        title="🚧 ⚠️ MAINTENANCE EN COURS ⚠️ 🚧",
        description=f"```diff\n- SERVEUR EN MAINTENANCE\n- SEULS LES ADMINS PEUVENT PARLER\n```\n**🔧 RAISON:** `{reason}`\n**👨‍💻 ACTIVÉ PAR:** {interaction.user.mention}",
        color=0xffa500
    )
    embed.set_image(url="https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif")
    embed.set_footer(text="Système de Maintenance | Mode Technique Activé")
    
    for channel in interaction.guild.text_channels:
        try:
            await channel.send(embed=embed)
        except:
            continue

@bot.tree.command(name="maintenance_off", description="Désactive le mode maintenance.")
@app_commands.checks.has_permissions(administrator=True)
async def maintenance_off(interaction: discord.Interaction):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["MAINTENANCE_MODE"] = False
    save_data()

    await interaction.response.send_message("✅ **Mode maintenance désactivé.**", ephemeral=True)
    
    embed = discord.Embed(
        title="🎉 ✨ MAINTENANCE TERMINÉE ✨ 🎉",
        description=f"```diff\n+ LE SERVEUR EST DE NOUVEAU OPÉRATIONNEL\n+ LES COMMUNICATIONS SONT RÉTABLIES\n```\n**👨‍💻 DÉSACTIVÉ PAR:** {interaction.user.mention}",
        color=0x00ff66
    )
    embed.set_image(url="https://media.giphy.com/media/TdfyKrN7pUfvy) giphy.gif") # Alternative GIF
    embed.set_footer(text="Système de Maintenance | Serveur Opérationnel")
    
    for channel in interaction.guild.text_channels:
        try:
            await channel.send(embed=embed)
        except:
            continue

@bot.tree.command(name="addword", description="Ajouter un mot à la liste des mots interdits.")
@app_commands.checks.has_permissions(administrator=True)
async def addword(interaction: discord.Interaction, word: str):
    guild_data = get_guild_data(interaction.guild.id)
    banned_words = guild_data["BANNED_WORDS"]
    if word.lower() not in banned_words:
        banned_words.append(word.lower())
        save_data()
        await interaction.response.send_message(f"🚫 Le mot `{word}` a été ajouté à la liste.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Le mot `{word}` est déjà dans la liste.", ephemeral=True)

@bot.tree.command(name="removeword", description="Retirer un mot de la liste des mots interdits.")
@app_commands.checks.has_permissions(administrator=True)
async def removeword(interaction: discord.Interaction, word: str):
    guild_data = get_guild_data(interaction.guild.id)
    banned_words = guild_data["BANNED_WORDS"]
    if word.lower() in banned_words:
        banned_words.remove(word.lower())
        save_data()
        await interaction.response.send_message(f"✅ Le mot `{word}` a été retiré de la liste.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Le mot `{word}` n'est pas dans la liste.", ephemeral=True)

@bot.tree.command(name="bannedwords", description="Affiche la liste des mots interdits.")
@app_commands.checks.has_permissions(administrator=True)
async def bannedwords(interaction: discord.Interaction):
    guild_data = get_guild_data(interaction.guild.id)
    words = ", ".join(guild_data["BANNED_WORDS"])
    await interaction.response.send_message(f"**Liste des mots bannis :**\n{words}", ephemeral=True)

@bot.tree.command(name="setlogchannel", description="Définit le canal pour les logs du bot.")
@app_commands.checks.has_permissions(administrator=True)
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["LOG_CHANNEL_ID"] = channel.id
    save_data()
    await interaction.response.send_message(f"📝 Le canal de logs a été défini sur {channel.mention}.")

# ---------------------------------------------------------------------------
# ----------------------- COMMANDES DE COMMUNICATION ------------------------
# ---------------------------------------------------------------------------

@bot.tree.command(name="say", description="Faire parler le bot.")
@app_commands.checks.has_permissions(administrator=True)
async def say(interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel
    try:
        await target_channel.send(message)
        await interaction.response.send_message(f"✅ Message envoyé dans {target_channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

@bot.tree.command(name="announce", description="Envoyer une annonce stylisée.")
@app_commands.checks.has_permissions(administrator=True)
async def announce(interaction: discord.Interaction, titre: str, message: str, ping_everyone: bool = False):
    embed = discord.Embed(
        title=f"📢 {titre}",
        description=message,
        color=0xffd700,
        timestamp=datetime.now()
    )
    embed.set_author(name="ANNONCE OFFICIELLE", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Annonce par {interaction.user.display_name}")
    
    content = "@everyone" if ping_everyone else ""
    
    try:
        await interaction.channel.send(content, embed=embed)
        await interaction.response.send_message("✅ Annonce envoyée.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

# ---------------------------------------------------------------------------
# -------------------------- COMMANDES GÉNÉRALES ---------------------------
# ---------------------------------------------------------------------------

@bot.tree.command(name="serverinfo", description="Affiche les informations du serveur.")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 Informations sur {guild.name}", color=guild.owner.color)
    embed.add_field(name="👑 Propriétaire", value=guild.owner.mention)
    embed.add_field(name="👥 Membres", value=guild.member_count)
    embed.add_field(name="📅 Créé le", value=guild.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="💬 Canaux", value=len(guild.text_channels) + len(guild.voice_channels))
    embed.add_field(name="🎭 Rôles", value=len(guild.roles))
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Affiche les informations d'un utilisateur.")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"👤 Informations sur {member.display_name}", color=member.color)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    embed.add_field(name="Nom d'utilisateur", value=member.name)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Compte créé le", value=member.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="A rejoint le serveur le", value=member.joined_at.strftime("%d/%m/%Y"))
    roles = [role.mention for role in member.roles[1:]] # Exclut @everyone
    embed.add_field(name=f"Rôles [{len(roles)}]", value=", ".join(roles) if roles else "Aucun", inline=False)
    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------------------------
# ------------------------- GESTION DES ÉVÉNEMENTS --------------------------
# ---------------------------------------------------------------------------

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    guild_data = get_guild_data(message.guild.id)

    # Bloquer les messages en mode maintenance
    if guild_data["MAINTENANCE_MODE"] and not message.author.guild_permissions.administrator:
        try:
            await message.delete()
        except:
            pass # On ignore les erreurs si le message est déjà supprimé
        return # On arrête le traitement du message

    # Automodération (mots interdits)
    if guild_data["AUTOMOD_ENABLED"] and not message.author.guild_permissions.administrator:
        content_lower = message.content.lower()
        if any(word in content_lower for word in guild_data["BANNED_WORDS"]):
            try:
                await message.delete()
                await message.author.send("⚠️ Votre message a été supprimé car il contenait un mot interdit.")
            except:
                pass
            return

     # Anti-spam
        user_id = message.author.id
        now = datetime.now()

        if user_id not in ANTI_SPAM:
            ANTI_SPAM[user_id] = []

        # Nettoyer les anciens messages (plus d'1 minute)
        ANTI_SPAM[user_id] = [msg_time for msg_time in ANTI_SPAM[user_id] if (now - msg_time).seconds < 60]

        # Ajouter ce message
        ANTI_SPAM[user_id].append(now)

        # Vérifier spam
        if len(ANTI_SPAM[user_id]) > MAX_MESSAGES_PER_MINUTE:
            try:
                await message.author.timeout(datetime.now() + timedelta(minutes=5), reason="Spam détecté")
                await message.channel.send(f"🔇 {message.author.mention} timeout pour spam (5min)")
            except:
                pass

        # Vérifier mentions excessives
        if len(message.mentions) > MAX_MENTIONS:
            await message.delete()
            try:
                await message.author.timeout(datetime.now() + timedelta(minutes=2), reason="Mentions excessives")
            except:
                pass

    await bot.process_commands(message)

@bot.event
async def on_member_join(member: discord.Member):
    guild_data = get_guild_data(member.guild.id)
    # Protection anti-raid
    if guild_data["RAID_PROTECTION"]:
        account_age = discord.utils.utcnow() - member.created_at
        if account_age.days < 7:
            try:
                await member.ban(reason="Protection anti-raid: Compte trop récent (< 7 jours)")
                # Log l'action si un canal de log est configuré
                log_channel_id = guild_data.get("LOG_CHANNEL_ID")
                if log_channel_id:
                    log_channel = member.guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(title="🛡️ Anti-Raid", description=f"{member.mention} a été banni (compte de moins de 7 jours).", color=0xff0000)
                        await log_channel.send(embed=embed)
            except:
                pass

# ---------------------------------------------------------------------------
# ------------------------------ DÉMARRAGE DU BOT ---------------------------
# ---------------------------------------------------------------------------
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
