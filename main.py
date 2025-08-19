import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
import asyncio
import logging
from dotenv import load_dotenv

# --- GESTION DES DONNÉES PAR SERVEUR ---
DATA_FILE = "data.json"
GUILD_DATA = {}

def load_data():
    global GUILD_DATA
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try: GUILD_DATA = json.load(f)
            except json.JSONDecodeError: GUILD_DATA = {}
    else:
        GUILD_DATA = {}

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(GUILD_DATA, f, indent=4)

def get_guild_data(guild_id):
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


# Configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

admin_group = app_commands.Group(
    name="admin",
    description="Commandes réservées aux administrateurs",
    default_permissions=discord.Permissions(administrator=True)
)

ANTI_SPAM = {}
MAX_MENTIONS = 5
MAX_MESSAGES_PER_MINUTE = 10

@bot.event
async def on_ready():
    load_data()
    print(f'✅ {bot.user} est connecté!')

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
    warn_data = {"reason": reason, "moderator": interaction.user.name, "date": datetime.now().strftime("%d/%m/%Y %H:%M")}
    warns[user_id].append(warn_data)
    save_data()
    embed = discord.Embed(title="⚠️ Avertissement", color=0xffff00)
    embed.add_field(name="Membre", value=member.mention)
    embed.add_field(name="Raison", value=reason)
    embed.add_field(name="Total warns", value=len(warns[user_id]))
    await interaction.response.send_message(embed=embed)
    if len(warns[user_id]) >= 3:
        try:
            await member.ban(reason="3 avertissements atteints")
            await interaction.followup.send(f"🔨 {member.mention} banni automatiquement (3 warns)")
        except: pass

@admin_group.command(name="warns", description="Voir les avertissements d'un membre")
async def view_warns(interaction: discord.Interaction, member: discord.Member):
    guild_data = get_guild_data(interaction.guild.id)
    warns = guild_data["WARNS"].get(str(member.id), [])
    if not warns:
        return await interaction.response.send_message(f"{member.mention} n'a aucun avertissement", ephemeral=True)
    embed = discord.Embed(title=f"⚠️ Avertissements de {member.name}", color=0xffff00)
    for i, warn_data in enumerate(warns, 1):
        embed.add_field(name=f"Warn #{i}", value=f"**Raison:** {warn_data['reason']}\n**Modérateur:** {warn_data['moderator']}\n**Date:** {warn_data['date']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="unwarn", description="Retirer un avertissement")
async def unwarn(interaction: discord.Interaction, member: discord.Member, warn_number: int):
    guild_data = get_guild_data(interaction.guild.id)
    warns = guild_data["WARNS"].get(str(member.id), [])
    if not (1 <= warn_number <= len(warns)):
        return await interaction.response.send_message("❌ Numéro d'avertissement invalide", ephemeral=True)
    removed_warn = warns.pop(warn_number - 1)
    save_data()
    embed = discord.Embed(title="✅ Avertissement retiré", color=0x00ff00)
    embed.add_field(name="Membre", value=member.mention)
    embed.add_field(name="Warn retiré", value=removed_warn['reason'])
    await interaction.response.send_message(embed=embed)

# COMMANDES DE SÉCURITÉ AVANCÉES
@admin_group.command(name="lockdown", description="Verrouiller le serveur")
async def lockdown(interaction: discord.Interaction, reason: str = "Urgence sécuritaire"):
    await interaction.response.send_message("🔒 **INITIALISATION DU VERROUILLAGE...**", ephemeral=True)
    try:
        lockdown_embed = discord.Embed(title="🚨 ⚠️ **ALERTE SÉCURITÉ MAXIMALE** ⚠️ 🚨", description=f"```diff\n- SERVEUR EN VERROUILLAGE TOTAL\n- ACCÈS COMMUNICATION SUSPENDU\n- SEULS LES ADMINISTRATEURS AUTORISÉS\n```\n\n**📋 RAISON:** `{reason}`\n**🔐 STATUT:** `VERROUILLÉ`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 MODÉRATEUR:** {interaction.user.mention}", color=0xff0000)
        lockdown_embed.set_image(url="https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif")
        lockdown_embed.set_thumbnail(url="https://media.giphy.com/media/xTiTnHXbRoaZ1B1Mo8/giphy.gif")
        lockdown_embed.add_field(name="🛡️ **PROTOCOLE DE SÉCURITÉ ACTIVÉ**", value="```yaml\n✅ Communications bloquées\n✅ Permissions révoquées\n✅ Surveillance active\n✅ Mode défensif engagé```", inline=False)
        lockdown_embed.set_footer(text="🔒 SYSTÈME DE SÉCURITÉ ASTRAL | VERROUILLAGE TOTAL ENGAGÉ", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")
        locked_channels = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=False)
                locked_channels += 1
            except: pass
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🚨" * 10, embed=lockdown_embed)
            except: pass
        await interaction.followup.send(f"✅ **VERROUILLAGE TERMINÉ** - {locked_channels} canaux sécurisés", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur lors du verrouillage", ephemeral=True)

@admin_group.command(name="unlock", description="Déverrouiller le serveur")
async def unlock(interaction: discord.Interaction):
    await interaction.response.send_message("🔓 **INITIALISATION DU DÉVERROUILLAGE...**", ephemeral=True)
    try:
        unlock_embed = discord.Embed(title="🎉 ✨ **LIBÉRATION TOTALE** ✨ 🎉", description=f"```diff\n+ SERVEUR DÉVERROUILLÉ AVEC SUCCÈS\n+ COMMUNICATIONS RÉTABLIES\n+ ACCÈS TOTAL RESTAURÉ\n```\n\n**🔓 STATUT:** `OPÉRATIONNEL`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 MODÉRATEUR:** {interaction.user.mention}\n**💬 MESSAGE:** `Bienvenue de retour ! Le serveur est maintenant pleinement opérationnel.`", color=0x00ff66)
        unlock_embed.set_image(url="https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif")
        unlock_embed.set_thumbnail(url="https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif")
        unlock_embed.add_field(name="🎊 **SYSTÈME LIBÉRÉ**", value="```yaml\n✅ Communications rétablies\n✅ Permissions restaurées\n✅ Mode normal activé\n✅ Activité autorisée```", inline=False)
        unlock_embed.add_field(name="🌟 **STATUT DU SERVEUR**", value="```css\n[OPÉRATIONNEL] Toutes les fonctionnalités disponibles\n[SÉCURISÉ] Protection active maintenue\n[STABLE] Système en fonctionnement optimal```", inline=False)
        unlock_embed.set_footer(text="🔓 SYSTÈME DE SÉCURITÉ ASTRAL | ACCÈS TOTAL RESTAURÉ", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")
        unlocked_channels = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=None)
                unlocked_channels += 1
            except: pass
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🎉" * 10, embed=unlock_embed)
            except: pass
        await interaction.followup.send(f"✅ **DÉVERROUILLAGE TERMINÉ** - {unlocked_channels} canaux libérés", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur lors du déverrouillage", ephemeral=True)

@admin_group.command(name="nuke", description="Supprimer tous les messages du canal")
async def nuke(interaction: discord.Interaction):
    channel_name = interaction.channel.name
    channel_position = interaction.channel.position
    channel_category = interaction.channel.category
    await interaction.response.send_message("💥 **PRÉPARATION DE LA DÉTONATION NUCLÉAIRE...**", ephemeral=True)
    countdown_embed = discord.Embed(title="💣 ⚠️ **ALERTE DÉTONATION IMMINENTE** ⚠️ 💣", description="```diff\n- PRÉPARATION DE LA DESTRUCTION TOTALE\n- ÉVACUATION NUMÉRIQUE EN COURS\n- NETTOYAGE RADICAL IMMINENT\n```", color=0xff4500)
    countdown_embed.set_image(url="https://media.giphy.com/media/oe33xf3B50fsc/giphy.gif")
    countdown_embed.add_field(name="⚡ COMPTE À REBOURS", value="```css\n[3] INITIALISATION...\n[2] CHARGEMENT...\n[1] DÉTONATION...\n[0] BOOM! 💥```", inline=False)
    await interaction.channel.send(embed=countdown_embed)
    await asyncio.sleep(3)
    try:
        await interaction.channel.delete()
        new_channel = await interaction.guild.create_text_channel(name=channel_name, position=channel_position, category=channel_category)
        nuke_embed = discord.Embed(title="🌋 💥 **DÉTONATION RÉUSSIE** 💥 🌋", description=f"```diff\n+ CANAL COMPLÈTEMENT PURIFIÉ\n+ DESTRUCTION TOTALE ACCOMPLIE\n+ RENAISSANCE NUMÉRIQUE INITIÉE\n```\n\n**💣 OPÉRATION:** `NUKE COMPLÈTE`\n**🔥 CANAL:** `#{channel_name}`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 OPÉRATEUR:** {interaction.user.mention}", color=0xff0000)
        nuke_embed.set_image(url="https://media.giphy.com/media/3oriO0OEd9QIDdllqo/giphy.gif")
        nuke_embed.set_thumbnail(url="https://media.giphy.com/media/l46CyJmS9KUbokzsI/giphy.gif")
        nuke_embed.add_field(name="☢️ **RAPPORT DE DÉTONATION**", value="```yaml\n✅ Messages éliminés: TOUS\n✅ Historique effacé: COMPLET\n✅ Canal purifié: 100%\n✅ Reconstruction: TERMINÉE```", inline=False)
        nuke_embed.add_field(name="🔄 **STATUT POST-APOCALYPSE**", value="```css\n[NOUVEAU] Canal fraîchement recréé\n[PROPRE] Aucun message résiduel\n[PRÊT] Disponible pour utilisation```", inline=False)
        nuke_embed.set_footer(text="💥 SYSTÈME DE PURIFICATION ASTRAL | NUKE RÉUSSI", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")
        await new_channel.send("💥" * 15, embed=nuke_embed)
        await new_channel.send("**🎉 BIENVENUE DANS LE NOUVEAU CANAL PURIFIÉ ! 🎉**")
    except:
        pass

@admin_group.command(name="massban", description="Bannir plusieurs utilisateurs")
async def massban(interaction: discord.Interaction, user_ids: str, reason: str = "Ban de masse"):
    await interaction.response.defer(ephemeral=True)
    ids = user_ids.split()
    banned_count = 0
    for user_id in ids:
        try:
            await interaction.guild.ban(discord.Object(id=int(user_id)), reason=reason)
            banned_count += 1
        except: continue
    await interaction.followup.send(f"🔨 {banned_count} utilisateurs bannis.")

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
    if word.lower() not in guild_data["BANNED_WORDS"]:
        guild_data["BANNED_WORDS"].append(word.lower())
        save_data()
        embed = discord.Embed(title="🚫 Mot ajouté", description=f"'{word}' ajouté aux mots bannis", color=0xff6b6b)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot est déjà banni", color=0xff0000)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="removeword", description="Retirer un mot banni")
async def removeword(interaction: discord.Interaction, word: str):
    guild_data = get_guild_data(interaction.guild.id)
    if word.lower() in guild_data["BANNED_WORDS"]:
        guild_data["BANNED_WORDS"].remove(word.lower())
        save_data()
        embed = discord.Embed(title="✅ Mot retiré", description=f"'{word}' retiré des mots bannis", color=0x00ff00)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot n'est pas dans la liste", color=0xff0000)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@admin_group.command(name="bannedwords", description="Voir la liste des mots bannis")
async def bannedwords(interaction: discord.Interaction):
    guild_data = get_guild_data(interaction.guild.id)
    if not guild_data["BANNED_WORDS"]:
        return await interaction.response.send_message("Aucun mot banni", ephemeral=True)
    embed = discord.Embed(title="🚫 Mots bannis", description="\n".join(guild_data["BANNED_WORDS"]), color=0xff6b6b)
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
        maintenance_embed = discord.Embed(title="🚧 ⚠️ **MAINTENANCE EN COURS** ⚠️ 🚧", description=f"```diff\n- SERVEUR EN MAINTENANCE TECHNIQUE\n- ACCÈS UTILISATEUR SUSPENDU\n- INTERVENTIONS ADMINISTRATIVES EN COURS\n```\n\n**🔧 RAISON:** `{reason}`\n**⚙️ STATUT:** `MAINTENANCE ACTIVE`\n**⏰ DÉBUT:** <t:{int(datetime.now().timestamp())}:F>\n**👨‍💻 TECHNICIEN:** {interaction.user.mention}", color=0xffa500)
        maintenance_embed.set_image(url="https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif")
        maintenance_embed.set_thumbnail(url="https://media.giphy.com/media/xTiTnHXbRoaZ1B1Mo8/giphy.gif")
        maintenance_embed.add_field(name="⚙️ **OPÉRATIONS EN COURS**", value="```yaml\n🔧 Maintenance système active\n🛠️ Interventions techniques\n🔄 Optimisations serveur\n⏸️ Communications suspendues```", inline=False)
        maintenance_embed.add_field(name="🚫 **RESTRICTIONS ACTIVES**", value="```css\n[BLOQUÉ] Messages utilisateurs\n[AUTORISÉ] Communications admin\n[ACTIF] Surveillance système\n[STANDBY] Fonctions normales```", inline=False)
        maintenance_embed.add_field(name="📋 **INFORMATIONS**", value=f"```fix\nDurée estimée: En cours d'évaluation\nImpact: Communications temporairement suspendues\nContact: Équipe administrative disponible```", inline=False)
        maintenance_embed.set_footer(text="🔧 SYSTÈME DE MAINTENANCE ASTRAL | MODE TECHNIQUE ACTIVÉ", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🚧" * 10, embed=maintenance_embed)
            except: pass
        await interaction.followup.send(f"✅ **MODE MAINTENANCE ACTIVÉ** - Serveur en maintenance technique", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur lors de l'activation maintenance", ephemeral=True)

@admin_group.command(name="maintenance_off", description="Mode maintenance OFF")
async def maintenance_off(interaction: discord.Interaction):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["MAINTENANCE_MODE"] = False
    save_data()
    await interaction.response.send_message("✅ **FINALISATION DE LA MAINTENANCE...**", ephemeral=True)
    try:
        end_maintenance_embed = discord.Embed(title="🎉 ✨ **MAINTENANCE TERMINÉE** ✨ 🎉", description=f"```diff\n+ MAINTENANCE TECHNIQUE COMPLÉTÉE\n+ SERVEUR PLEINEMENT OPÉRATIONNEL\n+ COMMUNICATIONS RÉTABLIES\n```\n\n**✅ STATUT:** `OPÉRATIONNEL`\n**⏰ FIN:** <t:{int(datetime.now().timestamp())}:F>\n**👨‍💻 TECHNICIEN:** {interaction.user.mention}\n**🔄 RÉSULTAT:** `Maintenance réussie - Système optimisé`", color=0x00ff66)
        end_maintenance_embed.set_image(url="https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif")
        end_maintenance_embed.set_thumbnail(url="https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif")
        end_maintenance_embed.add_field(name="🎊 **MAINTENANCE RÉUSSIE**", value="```yaml\n✅ Système entièrement opérationnel\n✅ Communications restaurées\n✅ Optimisations appliquées\n✅ Serveur stabilisé```", inline=False)
        end_maintenance_embed.add_field(name="🌟 **AMÉLIORATIONS APPORTÉES**", value="```css\n[OPTIMISÉ] Performances système\n[SÉCURISÉ] Protocoles de sécurité\n[STABLE] Fonctionnement optimal\n[DISPONIBLE] Toutes fonctionnalités```", inline=False)
        end_maintenance_embed.add_field(name="📢 **ANNONCE**", value="```fix\nLe serveur est maintenant pleinement fonctionnel !\nMerci de votre patience pendant la maintenance.\nToutes les fonctionnalités sont disponibles.```", inline=False)
        end_maintenance_embed.set_footer(text="✅ SYSTÈME DE MAINTENANCE ASTRAL | SERVEUR OPÉRATIONNEL", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🎉" * 10, embed=end_maintenance_embed)
                await channel.send("**🚀 LE SERVEUR EST DE RETOUR ! BIENVENUE ! 🚀**")
            except: pass
        await interaction.followup.send(f"✅ **MAINTENANCE TERMINÉE** - Serveur pleinement opérationnel", ephemeral=True)
    except:
        await interaction.followup.send("❌ Erreur lors de la fin de maintenance", ephemeral=True)

@admin_group.command(name="setlogchannel", description="Définir le canal de logs")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_data = get_guild_data(interaction.guild.id)
    guild_data["LOG_CHANNEL_ID"] = channel.id
    save_data()
    embed = discord.Embed(title="📝 Canal de logs défini", description=f"Logs dans {channel.mention}", color=0x0099ff)
    await interaction.response.send_message(embed=embed)

@admin_group.command(name="say", description="Faire parler le bot")
async def say(interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel
    try:
        await target_channel.send(message)
        embed = discord.Embed(title="✅ Message envoyé", description=f"Message envoyé dans {target_channel.mention}", color=0x00ff00)
        embed.add_field(name="Contenu", value=f"```{message[:1000]}```", inline=False)
        embed.add_field(name="Expéditeur", value=interaction.user.mention, inline=True)
        embed.add_field(name="Canal", value=target_channel.mention, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        guild_data = get_guild_data(interaction.guild.id)
        log_channel_id = guild_data.get("LOG_CHANNEL_ID")
        if log_channel_id:
            log_channel = bot.get_channel(log_channel_id)
            if log_channel and log_channel != target_channel:
                log_embed = discord.Embed(title="📤 Message bot envoyé", description=f"Message envoyé via le bot dans {target_channel.mention}", color=0x0099ff)
                log_embed.add_field(name="Contenu", value=f"```{message[:1000]}```", inline=False)
                log_embed.add_field(name="Administrateur", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Heure", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=True)
                await log_channel.send(embed=log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'envoi: {str(e)}", ephemeral=True)

@admin_group.command(name="embed", description="Envoyer un message embed via le bot")
async def send_embed(interaction: discord.Interaction, title: str, description: str, channel: discord.TextChannel = None, color: str = "0x0099ff"):
    target_channel = channel or interaction.channel
    try:
        embed_color = int(color.replace("0x", ""), 16)
        embed = discord.Embed(title=title, description=description, color=embed_color, timestamp=datetime.now())
        embed.set_footer(text=f"Message officiel • {interaction.guild.name}")
        await target_channel.send(embed=embed)
        confirm_embed = discord.Embed(title="✅ Embed envoyé", description=f"Embed envoyé dans {target_channel.mention}", color=0x00ff00)
        confirm_embed.add_field(name="Titre", value=title, inline=False)
        confirm_embed.add_field(name="Description", value=description[:1000], inline=False)
        confirm_embed.add_field(name="Expéditeur", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
        guild_data = get_guild_data(interaction.guild.id)
        log_channel_id = guild_data.get("LOG_CHANNEL_ID")
        if log_channel_id:
            log_channel = bot.get_channel(log_channel_id)
            if log_channel and log_channel != target_channel:
                log_embed = discord.Embed(title="📤 Embed bot envoyé", description=f"Embed envoyé via le bot dans {target_channel.mention}", color=0x0099ff)
                log_embed.add_field(name="Titre", value=title, inline=False)
                log_embed.add_field(name="Description", value=description[:1000], inline=False)
                log_embed.add_field(name="Administrateur", value=interaction.user.mention, inline=True)
                await log_channel.send(embed=log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'envoi: {str(e)}", ephemeral=True)

@admin_group.command(name="announce", description="Envoyer une annonce officielle")
async def announce(interaction: discord.Interaction, title: str, message: str, channel: discord.TextChannel = None, ping_everyone: bool = False):
    target_channel = channel or interaction.channel
    try:
        announce_embed = discord.Embed(title=f"📢 {title}", description=message, color=0xffd700, timestamp=datetime.now())
        announce_embed.set_footer(text=f"Annonce officielle • {interaction.guild.name}")
        announce_embed.set_author(name="ANNONCE OFFICIELLE", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        announce_embed.set_thumbnail(url="https://media.giphy.com/media/l0HlQoLBxzlnKRT8s/giphy.gif")
        content = "@everyone" if ping_everyone else ""
        await target_channel.send("🔔" * 5, content=content, embed=announce_embed)
        confirm_embed = discord.Embed(title="✅ Annonce publiée", description=f"Annonce envoyée dans {target_channel.mention}", color=0x00ff00)
        confirm_embed.add_field(name="Titre", value=title, inline=False)
        confirm_embed.add_field(name="Message", value=message[:1000], inline=False)
        confirm_embed.add_field(name="Ping everyone", value="Oui" if ping_everyone else "Non", inline=True)
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
        guild_data = get_guild_data(interaction.guild.id)
        log_channel_id = guild_data.get("LOG_CHANNEL_ID")
        if log_channel_id:
            log_channel = bot.get_channel(log_channel_id)
            if log_channel and log_channel != target_channel:
                log_embed = discord.Embed(title="📢 Annonce officielle publiée", description=f"Annonce publiée dans {target_channel.mention}", color=0xffd700)
                log_embed.add_field(name="Titre", value=title, inline=False)
                log_embed.add_field(name="Message", value=message[:1000], inline=False)
                log_embed.add_field(name="Administrateur", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Ping everyone", value="Oui" if ping_everyone else "Non", inline=True)
                await log_channel.send(embed=log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'envoi: {str(e)}", ephemeral=True)

@admin_group.command(name="dm", description="Envoyer un MP à un utilisateur via le bot")
async def send_dm(interaction: discord.Interaction, member: discord.Member, message: str):
    try:
        dm_embed = discord.Embed(title="📨 Message du serveur", description=message, color=0x0099ff, timestamp=datetime.now())
        dm_embed.set_footer(text=f"Message officiel de {interaction.guild.name}")
        dm_embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        await member.send(embed=dm_embed)
        confirm_embed = discord.Embed(title="✅ MP envoyé", description=f"Message privé envoyé à {member.mention}", color=0x00ff00)
        confirm_embed.add_field(name="Contenu", value=f"```{message[:1000]}```", inline=False)
        confirm_embed.add_field(name="Destinataire", value=member.mention, inline=True)
        confirm_embed.add_field(name="Expéditeur", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
        guild_data = get_guild_data(interaction.guild.id)
        log_channel_id = guild_data.get("LOG_CHANNEL_ID")
        if log_channel_id:
            log_channel = bot.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(title="📨 MP bot envoyé", description=f"Message privé envoyé via le bot à {member.mention}", color=0x0099ff)
                log_embed.add_field(name="Contenu", value=f"```{message[:1000]}```", inline=False)
                log_embed.add_field(name="Destinataire", value=member.mention, inline=True)
                log_embed.add_field(name="Administrateur", value=interaction.user.mention, inline=True)
                await log_channel.send(embed=log_embed)
    except discord.Forbidden:
        await interaction.response.send_message(f"❌ Impossible d'envoyer un MP à {member.mention} (MP fermés)", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors de l'envoi: {str(e)}", ephemeral=True)

@bot.tree.command(name="commands", description="Liste détaillée des commandes")
async def commands_list(interaction: discord.Interaction):
    embeds = []
    if interaction.user.guild_permissions.administrator:
        embed1 = discord.Embed(title="🔨 MODÉRATION DE BASE", color=0xff6b6b)
        embed1.add_field(name="/admin kick [membre] [raison]", value="Exclure un membre du serveur", inline=False)
        embed1.add_field(name="/admin ban [membre] [raison]", value="Bannir définitivement un membre", inline=False)
        embed1.add_field(name="/admin unban [ID_utilisateur] [raison]", value="Débannir un utilisateur avec son ID", inline=False)
        embed1.add_field(name="/admin mute [membre] [minutes] [raison]", value="Timeout un membre", inline=False)
        embed1.add_field(name="/admin unmute [membre]", value="Retirer le timeout d'un membre", inline=False)
        embed1.add_field(name="/admin clear [nombre]", value="Supprimer des messages (max 100)", inline=False)
        embeds.append(embed1)
        embed2 = discord.Embed(title="⚠️ SYSTÈME D'AVERTISSEMENTS", color=0xffff00)
        embed2.add_field(name="/admin warn [membre] [raison]", value="Avertir un membre (ban auto à 3)", inline=False)
        embed2.add_field(name="/admin warns [membre]", value="Voir les avertissements d'un membre", inline=False)
        embed2.add_field(name="/admin unwarn [membre] [numéro]", value="Retirer un avertissement", inline=False)
        embeds.append(embed2)
        embed3 = discord.Embed(title="🛡️ SÉCURITÉ AVANCÉE", color=0xff0000)
        embed3.add_field(name="/admin lockdown [raison]", value="🚨 Verrouiller TOUT le serveur", inline=False)
        embed3.add_field(name="/admin unlock", value="🎉 Déverrouiller le serveur", inline=False)
        embed3.add_field(name="/admin nuke", value="💥 Purifier un canal", inline=False)
        embed3.add_field(name="/admin massban [IDs] [raison]", value="🔨 Bannir plusieurs utilisateurs", inline=False)
        embed3.add_field(name="/admin antiraid [true/false]", value="🛡️ Protection anti-comptes récents", inline=False)
        embeds.append(embed3)
        embed4 = discord.Embed(title="🤖 AUTOMODÉRATION", color=0x9932cc)
        embed4.add_field(name="/admin automod [true/false]", value="Activer/désactiver l'automodération", inline=False)
        embed4.add_field(name="/admin addword [mot]", value="Ajouter un mot interdit", inline=False)
        embed4.add_field(name="/admin removeword [mot]", value="Retirer un mot interdit", inline=False)
        embed4.add_field(name="/admin bannedwords", value="Voir les mots interdits", inline=False)
        embeds.append(embed4)
        embed5 = discord.Embed(title="📤 MESSAGES VIA BOT", color=0x00aaff)
        embed5.add_field(name="/admin say [message] [canal]", value="Faire parler le bot", inline=False)
        embed5.add_field(name="/admin embed [titre] [description] ...", value="Envoyer un embed stylisé", inline=False)
        embed5.add_field(name="/admin announce [titre] [message] ...", value="Publier une annonce officielle", inline=False)
        embed5.add_field(name="/admin dm [membre] [message]", value="Envoyer un message privé", inline=False)
        embeds.append(embed5)
        embed6 = discord.Embed(title="⚙️ SYSTÈME & CONFIGURATION", color=0xffa500)
        embed6.add_field(name="/admin maintenance [raison]", value="🚧 Activer le mode maintenance", inline=False)
        embed6.add_field(name="/admin maintenance_off", value="✅ Désactiver le mode maintenance", inline=False)
        embed6.add_field(name="/admin setlogchannel [canal]", value="Définir le canal de logs", inline=False)
        embeds.append(embed6)
    embed_general = discord.Embed(title="📋 COMMANDES GÉNÉRALES", color=0x0099ff)
    embed_general.add_field(name="/commands", value="Afficher cette liste", inline=False)
    embed_general.add_field(name="/serverinfo", value="Informations du serveur", inline=False)
    embed_general.add_field(name="/userinfo [membre]", value="Informations d'un utilisateur", inline=False)
    embeds.append(embed_general)
    await interaction.response.send_message(embed=embeds[0], ephemeral=True)
    for embed in embeds[1:]:
        await interaction.followup.send(embed=embed, ephemeral=True)

# ÉVÉNEMENTS DE SÉCURITÉ
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild: return
    guild_data = get_guild_data(message.guild.id)
    if guild_data["MAINTENANCE_MODE"] and not message.author.guild_permissions.administrator:
        try:
            await message.delete()
            await message.author.send(f"🔧 Serveur en maintenance: {guild_data['MAINTENANCE_REASON']}")
        except: pass
        return
    if guild_data["AUTOMOD_ENABLED"] and not message.author.guild_permissions.administrator:
        if any(word in message.content.lower() for word in guild_data["BANNED_WORDS"]):
            try:
                await message.delete()
                await message.author.send("⚠️ Message supprimé: mot interdit détecté")
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
                await message.channel.send(f"🔇 {message.author.mention} timeout pour spam (5min)")
            except: pass
        if len(message.mentions) > MAX_MENTIONS:
            try:
                await message.delete()
                await message.author.timeout(discord.utils.utcnow() + timedelta(minutes=2), reason="Mentions excessives")
            except: pass

@bot.event
async def on_member_join(member: discord.Member):
    guild_data = get_guild_data(member.guild.id)
    if guild_data["RAID_PROTECTION"] and (discord.utils.utcnow() - member.created_at).days < 7:
        try:
            await member.ban(reason="Anti-raid: Compte trop récent")
            log_channel_id = guild_data["LOG_CHANNEL_ID"]
            if log_channel_id:
                log_channel = member.guild.get_channel(log_channel_id)
                if log_channel:
                    await log_channel.send(f"🛡️ {member.mention} banni (compte trop récent).")
        except: pass

@bot.event
async def on_member_remove(member: discord.Member):
    guild_data = get_guild_data(member.guild.id)
    log_channel_id = guild_data["LOG_CHANNEL_ID"]
    if log_channel_id:
        log_channel = member.guild.get_channel(log_channel_id)
        if log_channel:
            await log_channel.send(f"👋 {member.name} a quitté le serveur.")

# --- CORRECTION FINALE : Utilisation du setup_hook pour un chargement fiable ---
async def setup_hook():
    bot.tree.add_command(admin_group)
    await bot.tree.sync()
    print("Commandes synchronisées via setup_hook.")

bot.setup_hook = setup_hook

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
