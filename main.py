
import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import json
import asyncio

# Configuration
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Variables globales
LOG_CHANNEL_ID = None
MAINTENANCE_MODE = False
MAINTENANCE_REASON = ""
ANTI_SPAM = {}
WARNS = {}
AUTOMOD_ENABLED = True
RAID_PROTECTION = True
BANNED_WORDS = ["spam", "hack", "scam"]
MAX_MENTIONS = 5
MAX_MESSAGES_PER_MINUTE = 10

@bot.event
async def on_ready():
    print(f'✅ {bot.user} est connecté!')
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commandes synchronisées')
    except Exception as e:
        print(f'❌ Erreur sync: {e}')

# COMMANDES DE MODÉRATION BASIQUES
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

# SYSTÈME D'AVERTISSEMENTS
@bot.tree.command(name="warn", description="Avertir un membre")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    user_id = str(member.id)
    if user_id not in WARNS:
        WARNS[user_id] = []
    
    warn_data = {
        "reason": reason,
        "moderator": interaction.user.name,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    WARNS[user_id].append(warn_data)
    
    embed = discord.Embed(title="⚠️ Avertissement", color=0xffff00)
    embed.add_field(name="Membre", value=member.mention)
    embed.add_field(name="Raison", value=reason)
    embed.add_field(name="Total warns", value=len(WARNS[user_id]))
    
    await interaction.response.send_message(embed=embed)
    
    # Auto-sanction selon le nombre de warns
    warn_count = len(WARNS[user_id])
    if warn_count >= 3:
        try:
            await member.ban(reason="3 avertissements atteints")
            await interaction.followup.send(f"🔨 {member.mention} banni automatiquement (3 warns)")
        except:
            pass

@bot.tree.command(name="warns", description="Voir les avertissements d'un membre")
async def view_warns(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    user_id = str(member.id)
    warns = WARNS.get(user_id, [])
    
    if not warns:
        return await interaction.response.send_message(f"{member.mention} n'a aucun avertissement", ephemeral=True)
    
    embed = discord.Embed(title=f"⚠️ Avertissements de {member.name}", color=0xffff00)
    for i, warn in enumerate(warns, 1):
        embed.add_field(
            name=f"Warn #{i}",
            value=f"**Raison:** {warn['reason']}\n**Modérateur:** {warn['moderator']}\n**Date:** {warn['date']}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="unwarn", description="Retirer un avertissement")
async def unwarn(interaction: discord.Interaction, member: discord.Member, warn_number: int):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    user_id = str(member.id)
    warns = WARNS.get(user_id, [])
    
    if not warns or warn_number < 1 or warn_number > len(warns):
        return await interaction.response.send_message("❌ Numéro d'avertissement invalide", ephemeral=True)
    
    removed_warn = warns.pop(warn_number - 1)
    embed = discord.Embed(title="✅ Avertissement retiré", color=0x00ff00)
    embed.add_field(name="Membre", value=member.mention)
    embed.add_field(name="Warn retiré", value=removed_warn['reason'])
    
    await interaction.response.send_message(embed=embed)

# COMMANDES DE SÉCURITÉ AVANCÉES
@bot.tree.command(name="lockdown", description="Verrouiller le serveur")
async def lockdown(interaction: discord.Interaction, reason: str = "Urgence sécuritaire"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    await interaction.response.send_message("🔒 **INITIALISATION DU VERROUILLAGE...**", ephemeral=True)
    
    try:
        # Créer l'embed cinématique
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
        lockdown_embed.set_footer(text="🔒 SYSTÈME DE SÉCURITÉ ASTRAL | VERROUILLAGE TOTAL ENGAGÉ", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")
        
        # Verrouiller tous les canaux
        locked_channels = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=False)
                locked_channels += 1
            except:
                pass
        
        # Envoyer dans tous les canaux texte
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🚨" * 10)
                await channel.send(embed=lockdown_embed)
                await channel.send("🚨" * 10)
            except:
                pass
        
        # Confirmer dans le canal de commande
        await interaction.followup.send(f"✅ **VERROUILLAGE TERMINÉ** - {locked_channels} canaux sécurisés", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send("❌ Erreur lors du verrouillage", ephemeral=True)

@bot.tree.command(name="unlock", description="Déverrouiller le serveur")
async def unlock(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    await interaction.response.send_message("🔓 **INITIALISATION DU DÉVERROUILLAGE...**", ephemeral=True)
    
    try:
        # Créer l'embed cinématique
        unlock_embed = discord.Embed(
            title="🎉 ✨ **LIBÉRATION TOTALE** ✨ 🎉",
            description=f"```diff\n+ SERVEUR DÉVERROUILLÉ AVEC SUCCÈS\n+ COMMUNICATIONS RÉTABLIES\n+ ACCÈS TOTAL RESTAURÉ\n```\n\n**🔓 STATUT:** `OPÉRATIONNEL`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 MODÉRATEUR:** {interaction.user.mention}\n**💬 MESSAGE:** `Bienvenue de retour ! Le serveur est maintenant pleinement opérationnel.`",
            color=0x00ff66
        )
        unlock_embed.set_image(url="https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif")
        unlock_embed.set_thumbnail(url="https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif")
        unlock_embed.add_field(
            name="🎊 **SYSTÈME LIBÉRÉ**",
            value="```yaml\n✅ Communications rétablies\n✅ Permissions restaurées\n✅ Mode normal activé\n✅ Activité autorisée```",
            inline=False
        )
        unlock_embed.add_field(
            name="🌟 **STATUT DU SERVEUR**",
            value="```css\n[OPÉRATIONNEL] Toutes les fonctionnalités disponibles\n[SÉCURISÉ] Protection active maintenue\n[STABLE] Système en fonctionnement optimal```",
            inline=False
        )
        unlock_embed.set_footer(text="🔓 SYSTÈME DE SÉCURITÉ ASTRAL | ACCÈS TOTAL RESTAURÉ", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")
        
        # Déverrouiller tous les canaux
        unlocked_channels = 0
        for channel in interaction.guild.text_channels:
            try:
                await channel.set_permissions(interaction.guild.default_role, send_messages=None)
                unlocked_channels += 1
            except:
                pass
        
        # Envoyer dans tous les canaux texte
        for channel in interaction.guild.text_channels:
            try:
                await channel.send("🎉" * 10)
                await channel.send(embed=unlock_embed)
                await channel.send("🎊" * 10)
            except:
                pass
        
        # Confirmer dans le canal de commande
        await interaction.followup.send(f"✅ **DÉVERROUILLAGE TERMINÉ** - {unlocked_channels} canaux libérés", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send("❌ Erreur lors du déverrouillage", ephemeral=True)

@bot.tree.command(name="nuke", description="Supprimer tous les messages du canal")
async def nuke(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    channel_name = interaction.channel.name
    channel_position = interaction.channel.position
    channel_category = interaction.channel.category
    
    # Message de préparation
    await interaction.response.send_message("💥 **PRÉPARATION DE LA DÉTONATION NUCLÉAIRE...**", ephemeral=True)
    
    # Countdown dramatique
    countdown_embed = discord.Embed(
        title="💣 ⚠️ **ALERTE DÉTONATION IMMINENTE** ⚠️ 💣",
        description="```diff\n- PRÉPARATION DE LA DESTRUCTION TOTALE\n- ÉVACUATION NUMÉRIQUE EN COURS\n- NETTOYAGE RADICAL IMMINENT\n```",
        color=0xff4500
    )
    countdown_embed.set_image(url="https://media.giphy.com/media/oe33xf3B50fsc/giphy.gif")
    countdown_embed.add_field(name="⚡ COMPTE À REBOURS", value="```css\n[3] INITIALISATION...\n[2] CHARGEMENT...\n[1] DÉTONATION...\n[0] BOOM! 💥```", inline=False)
    
    countdown_msg = await interaction.channel.send(embed=countdown_embed)
    
    # Attendre un peu pour l'effet dramatique
    await asyncio.sleep(3)
    
    try:
        await interaction.channel.delete()
        new_channel = await interaction.guild.create_text_channel(
            name=channel_name,
            position=channel_position,
            category=channel_category
        )
        
        # Message post-nuke cinématique
        nuke_embed = discord.Embed(
            title="🌋 💥 **DÉTONATION RÉUSSIE** 💥 🌋",
            description=f"```diff\n+ CANAL COMPLÈTEMENT PURIFIÉ\n+ DESTRUCTION TOTALE ACCOMPLIE\n+ RENAISSANCE NUMÉRIQUE INITIÉE\n```\n\n**💣 OPÉRATION:** `NUKE COMPLÈTE`\n**🔥 CANAL:** `#{channel_name}`\n**⏰ HEURE:** <t:{int(datetime.now().timestamp())}:F>\n**👤 OPÉRATEUR:** {interaction.user.mention}",
            color=0xff0000
        )
        nuke_embed.set_image(url="https://media.giphy.com/media/3oriO0OEd9QIDdllqo/giphy.gif")
        nuke_embed.set_thumbnail(url="https://media.giphy.com/media/l46CyJmS9KUbokzsI/giphy.gif")
        nuke_embed.add_field(
            name="☢️ **RAPPORT DE DÉTONATION**",
            value="```yaml\n✅ Messages éliminés: TOUS\n✅ Historique effacé: COMPLET\n✅ Canal purifié: 100%\n✅ Reconstruction: TERMINÉE```",
            inline=False
        )
        nuke_embed.add_field(
            name="🔄 **STATUT POST-APOCALYPSE**",
            value="```css\n[NOUVEAU] Canal fraîchement recréé\n[PROPRE] Aucun message résiduel\n[PRÊT] Disponible pour utilisation```",
            inline=False
        )
        nuke_embed.set_footer(text="💥 SYSTÈME DE PURIFICATION ASTRAL | NUKE RÉUSSI", icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png")
        
        await new_channel.send("💥" * 15)
        await new_channel.send(embed=nuke_embed)
        await new_channel.send("☢️" * 15)
        await new_channel.send("**🎉 BIENVENUE DANS LE NOUVEAU CANAL PURIFIÉ ! 🎉**")
        
    except Exception as e:
        pass

@bot.tree.command(name="massban", description="Bannir plusieurs utilisateurs")
async def massban(interaction: discord.Interaction, user_ids: str, reason: str = "Ban de masse"):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    await interaction.response.defer()
    
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

@bot.tree.command(name="antiraid", description="Activer/désactiver la protection anti-raid")
async def antiraid(interaction: discord.Interaction, enabled: bool = True):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    global RAID_PROTECTION
    RAID_PROTECTION = enabled
    
    status = "activée" if enabled else "désactivée"
    color = 0x00ff00 if enabled else 0xff0000
    embed = discord.Embed(title="🛡️ Protection Anti-Raid", description=f"Protection {status}", color=color)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="automod", description="Activer/désactiver l'automodération")
async def automod(interaction: discord.Interaction, enabled: bool = True):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    global AUTOMOD_ENABLED
    AUTOMOD_ENABLED = enabled
    
    status = "activée" if enabled else "désactivée"
    color = 0x00ff00 if enabled else 0xff0000
    embed = discord.Embed(title="🤖 Automodération", description=f"Automod {status}", color=color)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addword", description="Ajouter un mot banni")
async def addword(interaction: discord.Interaction, word: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    if word.lower() not in BANNED_WORDS:
        BANNED_WORDS.append(word.lower())
        embed = discord.Embed(title="🚫 Mot ajouté", description=f"'{word}' ajouté aux mots bannis", color=0xff6b6b)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot est déjà banni", color=0xff0000)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="removeword", description="Retirer un mot banni")
async def removeword(interaction: discord.Interaction, word: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    if word.lower() in BANNED_WORDS:
        BANNED_WORDS.remove(word.lower())
        embed = discord.Embed(title="✅ Mot retiré", description=f"'{word}' retiré des mots bannis", color=0x00ff00)
    else:
        embed = discord.Embed(title="❌ Erreur", description="Ce mot n'est pas dans la liste", color=0xff0000)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="bannedwords", description="Voir la liste des mots bannis")
async def bannedwords(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    if not BANNED_WORDS:
        return await interaction.response.send_message("Aucun mot banni", ephemeral=True)
    
    embed = discord.Embed(title="🚫 Mots bannis", description="\n".join(BANNED_WORDS), color=0xff6b6b)
    await interaction.response.send_message(embed=embed, ephemeral=True)

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

@bot.tree.command(name="setlogchannel", description="Définir le canal de logs")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Commande admin uniquement", ephemeral=True)
    
    global LOG_CHANNEL_ID
    LOG_CHANNEL_ID = channel.id
    
    embed = discord.Embed(title="📝 Canal de logs défini", description=f"Logs dans {channel.mention}", color=0x0099ff)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Informations du serveur")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 {guild.name}", color=0x0099ff)
    embed.add_field(name="Membres", value=guild.member_count)
    embed.add_field(name="Canaux", value=len(guild.channels))
    embed.add_field(name="Rôles", value=len(guild.roles))
    embed.add_field(name="Créé le", value=guild.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Propriétaire", value=guild.owner.mention if guild.owner else "Inconnu")
    embed.add_field(name="Niveau de vérification", value=str(guild.verification_level).title())
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Informations d'un utilisateur")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    if member is None:
        member = interaction.user
    
    embed = discord.Embed(title=f"👤 {member.name}", color=member.color)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Surnom", value=member.nick or "Aucun")
    embed.add_field(name="Rejoint le", value=member.joined_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Compte créé", value=member.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Rôles", value=len(member.roles) - 1)
    embed.add_field(name="Status", value=str(member.status).title())
    
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="commands", description="Liste détaillée des commandes")
async def commands_list(interaction: discord.Interaction):
    embeds = []
    
    if interaction.user.guild_permissions.administrator:
        # Embed 1: Modération de base
        embed1 = discord.Embed(title="🔨 MODÉRATION DE BASE", color=0xff6b6b)
        embed1.add_field(
            name="/kick [membre] [raison]", 
            value="Exclure un membre du serveur (il peut revenir avec une invitation)", 
            inline=False
        )
        embed1.add_field(
            name="/ban [membre] [raison]", 
            value="Bannir définitivement un membre (ne peut plus rejoindre)", 
            inline=False
        )
        embed1.add_field(
            name="/unban [ID_utilisateur] [raison]", 
            value="Débannir un utilisateur avec son ID Discord", 
            inline=False
        )
        embed1.add_field(
            name="/mute [membre] [minutes] [raison]", 
            value="Timeout un membre (ne peut plus parler pendant X minutes)", 
            inline=False
        )
        embed1.add_field(
            name="/unmute [membre]", 
            value="Retirer le timeout d'un membre", 
            inline=False
        )
        embed1.add_field(
            name="/clear [nombre]", 
            value="Supprimer X messages du canal (max 100)", 
            inline=False
        )
        embeds.append(embed1)
        
        # Embed 2: Système d'avertissements
        embed2 = discord.Embed(title="⚠️ SYSTÈME D'AVERTISSEMENTS", color=0xffff00)
        embed2.add_field(
            name="/warn [membre] [raison]", 
            value="Donner un avertissement à un membre (ban auto à 3 warns)", 
            inline=False
        )
        embed2.add_field(
            name="/warns [membre]", 
            value="Voir tous les avertissements d'un membre", 
            inline=False
        )
        embed2.add_field(
            name="/unwarn [membre] [numéro]", 
            value="Retirer un avertissement spécifique d'un membre", 
            inline=False
        )
        embeds.append(embed2)
        
        # Embed 3: Sécurité avancée
        embed3 = discord.Embed(title="🛡️ SÉCURITÉ AVANCÉE", color=0xff0000)
        embed3.add_field(
            name="/lockdown [raison]", 
            value="Verrouiller TOUT le serveur (personne ne peut parler)", 
            inline=False
        )
        embed3.add_field(
            name="/unlock", 
            value="Déverrouiller le serveur (rétablir la communication)", 
            inline=False
        )
        embed3.add_field(
            name="/nuke", 
            value="SUPPRIMER TOUS les messages du canal actuel (recrée le canal)", 
            inline=False
        )
        embed3.add_field(
            name="/massban [IDs séparés par espaces] [raison]", 
            value="Bannir plusieurs utilisateurs en une fois avec leurs IDs", 
            inline=False
        )
        embed3.add_field(
            name="/antiraid [true/false]", 
            value="Activer/désactiver protection auto (ban comptes récents <7j)", 
            inline=False
        )
        embeds.append(embed3)
        
        # Embed 4: Automodération
        embed4 = discord.Embed(title="🤖 AUTOMODÉRATION", color=0x9932cc)
        embed4.add_field(
            name="/automod [true/false]", 
            value="Activer/désactiver la modération automatique", 
            inline=False
        )
        embed4.add_field(
            name="/addword [mot]", 
            value="Ajouter un mot à la liste des mots interdits", 
            inline=False
        )
        embed4.add_field(
            name="/removeword [mot]", 
            value="Retirer un mot de la liste des mots interdits", 
            inline=False
        )
        embed4.add_field(
            name="/bannedwords", 
            value="Voir la liste complète des mots interdits", 
            inline=False
        )
        embed4.add_field(
            name="🔧 Protections automatiques :", 
            value="• Anti-spam (timeout 5min si >10 msg/min)\n• Anti-mentions (max 5 mentions/msg)\n• Filtrage mots interdits\n• Blocage pendant maintenance", 
            inline=False
        )
        embeds.append(embed4)
        
        # Embed 5: Système
        embed5 = discord.Embed(title="⚙️ SYSTÈME & CONFIGURATION", color=0xffa500)
        embed5.add_field(
            name="/maintenance [raison]", 
            value="Activer mode maintenance (seuls les admins peuvent parler)", 
            inline=False
        )
        embed5.add_field(
            name="/maintenance_off", 
            value="Désactiver le mode maintenance", 
            inline=False
        )
        embed5.add_field(
            name="/setlogchannel [canal]", 
            value="Définir le canal où les logs seront envoyés", 
            inline=False
        )
        embed5.add_field(
            name="/serverinfo", 
            value="Afficher les informations détaillées du serveur", 
            inline=False
        )
        embeds.append(embed5)
    
    # Embed pour tous les utilisateurs
    embed_general = discord.Embed(title="📋 COMMANDES GÉNÉRALES", color=0x0099ff)
    embed_general.add_field(
        name="/commands", 
        value="Afficher cette liste détaillée de toutes les commandes", 
        inline=False
    )
    embed_general.add_field(
        name="/userinfo [membre]", 
        value="Voir les informations d'un utilisateur (ou vous-même si aucun membre spécifié)", 
        inline=False
    )
    
    if interaction.user.guild_permissions.administrator:
        embed_general.add_field(
            name="🔑 ACCÈS ADMIN", 
            value="Vous avez accès à toutes les commandes de modération !", 
            inline=False
        )
    else:
        embed_general.add_field(
            name="🚫 ACCÈS LIMITÉ", 
            value="Vous n'avez accès qu'aux commandes générales", 
            inline=False
        )
    
    embeds.append(embed_general)
    
    # Envoyer le premier embed
    await interaction.response.send_message(embed=embeds[0], ephemeral=True)
    
    # Envoyer les autres embeds
    for embed in embeds[1:]:
        await interaction.followup.send(embed=embed, ephemeral=True)

# ÉVÉNEMENTS DE SÉCURITÉ
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
    
    # Automodération
    if AUTOMOD_ENABLED and not message.author.guild_permissions.administrator:
        # Vérifier mots bannis
        content_lower = message.content.lower()
        for word in BANNED_WORDS:
            if word in content_lower:
                await message.delete()
                try:
                    await message.author.send(f"⚠️ Message supprimé: mot interdit détecté")
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
async def on_member_join(member):
    if RAID_PROTECTION:
        # Vérifier compte récent (moins de 7 jours)
        account_age = datetime.now() - member.created_at.replace(tzinfo=None)
        if account_age.days < 7:
            try:
                await member.ban(reason="Protection anti-raid: compte trop récent")
                if LOG_CHANNEL_ID:
                    channel = bot.get_channel(LOG_CHANNEL_ID)
                    if channel:
                        embed = discord.Embed(title="🛡️ Anti-raid", description=f"{member.mention} banni (compte récent)", color=0xff0000)
                        await channel.send(embed=embed)
            except:
                pass

@bot.event
async def on_member_remove(member):
    if LOG_CHANNEL_ID:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="👋 Membre parti", description=f"{member.name} a quitté", color=0xffa500)
            await channel.send(embed=embed)

# DÉMARRAGE
if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        print("❌ Token manquant dans les Secrets!")
    else:
        bot.run(token)
